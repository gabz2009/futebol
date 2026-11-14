"""
=====================================================================
 TESTES DA PREPARAÇÃO DO DATA WAREHOUSE (esquema em estrela)
=====================================================================
 Testam a transformação (func/warehouse.py), que não precisa do
 PostgreSQL. O carregamento em si é verificado pelo controlo W01.
=====================================================================
"""
import datetime

import pandas as pd

import configuracao as cfg
import func.warehouse as warehouse


def equipas():
    return pd.DataFrame({"Equipa": ["Benfica", "Porto", "Belenenses"],
                         "NomeApresentacao": ["SL Benfica", "FC Porto", "Belenenses"],
                         "EmblemaURL": ["b.png", "p.png", "x.png"]})


def calendario():
    return pd.DataFrame({"JogoID": ["j1", "j2", "j3"], "Jornada": [1, 1, 2],
                         "Data": ["2026-08-08", "2026-08-01", "2026-08-15"],
                         "EquipaCasa": ["Benfica", "Porto", "Porto"], "EquipaFora": ["Porto", "Benfica", "Benfica"],
                         "Estado": ["FINISHED", "POSTPONED", "TIMED"]})


def test_so_as_equipas_da_epoca_atual():
    assert warehouse.dim_equipa(equipas(), calendario())["Equipa"].tolist() == ["Benfica", "Porto"]


def test_jogo_com_nomes_emblemas_e_golos_vazios():
    previsoes = pd.DataFrame({"JogoID": ["j1", "j3"], "Jornada": [1, 2], "Data": ["2026-08-08", "2026-08-15"],
                              "Hora": ["20:30", "18:00"], "EquipaCasa": ["Benfica", "Porto"],
                              "EquipaFora": ["Porto", "Benfica"], "Estado": ["FINISHED", "TIMED"],
                              "Tipo": ["Jogado", "Próxima jornada"], "GolosCasa": [2.0, None],
                              "GolosFora": [1.0, None], "Resultado": ["H", None], "FonteResultado": ["API", None]})
    jogos = warehouse.dim_jogo(previsoes, warehouse.dim_equipa(equipas(), calendario())).set_index("JogoID")
    assert jogos.loc["j1", ["NomeCasa", "EmblemaFora"]].tolist() == ["SL Benfica", "p.png"]
    assert jogos.loc["j1", "GolosCasa"] == 2 and pd.isna(jogos.loc["j3", "GolosCasa"])
    assert jogos.loc["j1", "Hora"] == datetime.time(20, 30)


def test_avaliacao_oficial_sem_datacorte_e_arredondada():
    avaliacao = pd.DataFrame({"JogoID": ["j1"], "Epoca": [cfg.EPOCA_ATUAL], "Jornada": [10],
                              "DataCorte": ["2026-10-30"], "Data": ["2026-10-30"], "ProbCasa": [0.0789123],
                              "ProbEmpate": [0.1810877], "ProbFora": [0.74], "Previsto": ["A"], "Resultado": ["A"],
                              "Acerto": [1.0], "LogLoss": [0.30110509], "RPS": [0.04], "ProbOddsCasa": [None],
                              "ProbOddsEmpate": [None], "ProbOddsFora": [None]})
    fato = warehouse.fato_avaliacao_oficial(avaliacao)
    assert "DataCorte" not in fato.columns and "Resultado" not in fato.columns     # o resultado está na dim_jogo
    assert fato.loc[0, "ProbCasa"] == 0.0789 and fato.loc[0, "LogLoss"] == 0.3011
    assert str(fato["Acerto"].dtype) == "Int64"


def test_env_com_comentarios_e_caracteres_especiais(tmp_path):
    caminho = tmp_path / ".env"
    caminho.write_text("# comentário\nPG_HOST=localhost\nPG_PALAVRA_PASSE=a@b=c/d\n", encoding="utf-8")
    assert warehouse.ler_env(caminho) == {"PG_HOST": "localhost", "PG_PALAVRA_PASSE": "a@b=c/d"}

def test_jornadas_com_inicio_da_epoca_e_proxima():
    previsoes = pd.DataFrame({"Jornada": [1, 1, 2], "Tipo": ["Jogado", "Provisória", "Próxima jornada"]})
    classificacao = pd.DataFrame({"Jornada": [1, 1], "Equipa": ["Benfica", "Porto"]})
    jornadas = warehouse.dim_jornada(calendario(), previsoes, classificacao).set_index("Jornada")
    assert jornadas.loc[0, "NomeCurto"] == "Início" and jornadas.loc[2, "NomeCurto"] == "J2"
    # O j2 (adiado, 01/08) não conta: a jornada 1 começa a 08/08
    assert jornadas.loc[1, "DataInicio"] == datetime.date(2026, 8, 8) == jornadas.loc[0, "DataInicio"]
    # A jornada 2 é a próxima: o rótulo é "Próxima" (o que o segmentador do Power BI guarda)
    assert jornadas["Estado"].tolist() == ["Início", "Jogada", "Próxima"]
    assert jornadas["Rotulo"].tolist() == ["Início", "J1", "Próxima"]
    # A última jornada com classificação é a 1: rótulo "Atual" na página da classificação
    assert jornadas["RotuloClassificacao"].tolist() == ["Início", "Atual", "J2"]
    assert jornadas["TemClassificacao"].tolist() == [0, 1, 0]

def test_variacao_da_posicao_entre_jornadas():
    # Jornada 1: Benfica 1.º, Porto 2.º. Jornada 2: trocam
    colunas = {c: 0 for c in warehouse.COLUNAS_CLASSIFICACAO if c != "Posicao"}
    classificacao = pd.DataFrame({"Jornada": [1, 1, 2, 2], "Equipa": ["Benfica", "Porto", "Benfica", "Porto"],
                                  "Posicao": [1, 2, 2, 1], **colunas})
    fato = warehouse.fato_classificacao_jornada(classificacao).set_index(["Jornada", "Equipa"])
    assert fato.loc[(2, "Porto"), "VariacaoPosicao"] == 1           # subiu um lugar
    assert fato.loc[(2, "Benfica"), "VariacaoPosicao"] == -1        # desceu um lugar
    assert pd.isna(fato.loc[(1, "Porto"), "VariacaoPosicao"])       # na 1.ª jornada não há anterior

def previsoes_notebook(modelo, log_loss, fase="Teste"):
    """4 jogos de um modelo, com o log loss de cada jogo."""
    return pd.DataFrame({"JogoID": ["a", "b", "c", "d"], "Epoca": "25-26", "Fase": fase, "Modelo": modelo,
                         "Resultado": ["H", "D", "A", "H"], "Acerto": [1.0, 0.0, 1.0, 0.0],
                         "LogLoss": log_loss, "RPS": 0.2, "ProbH": [0.75, 0.40, 0.20, 0.31],
                         "ProbD": 0.25, "ProbA": [0.0, 0.35, 0.55, 0.44]})


def test_avaliacao_junta_nomes_e_so_fica_com_os_modelos_do_relatorio():
    tabela = pd.concat([previsoes_notebook("Ordinal + DC + GB", 0.9), previsoes_notebook("Regressão, só Elo", 0.9)])
    preparada = warehouse.preparar_avaliacao(tabela)
    assert set(preparada["Modelo"]) == {"Modelo final"}


def test_diferenca_para_as_odds_de_abertura():
    tabela = pd.concat([previsoes_notebook("Odds de abertura", [0.9, 1.0, 0.8, 1.1]),
                        previsoes_notebook("Modelo final", [0.8, 0.9, 0.7, 1.0])])
    avaliacao = warehouse.fato_avaliacao_modelos(tabela, pd.DataFrame(columns=["Fase", "Modelo", "ECE"]))
    final = avaliacao.set_index("Modelo").loc["Modelo final"]
    referencia = avaliacao.set_index("Modelo").loc["Odds de abertura"]
    assert final["DifReferencia"] == -0.1                       # 0,1 melhor em todos os jogos
    assert final["DifInferior"] == final["DifSuperior"] == -0.1  # sempre igual: o intervalo não tem largura
    assert referencia["DifReferencia"] == referencia["DifInferior"] == referencia["DifSuperior"] == 0
    assert final["Jogos"] == 4


def test_calibracao_por_resultado_e_faixa(monkeypatch):
    monkeypatch.setattr(cfg, "MINIMO_JOGOS_FAIXA", 2)
    calibracao = warehouse.fato_calibracao(previsoes_notebook("Modelo final", 0.9))
    # Empate: os 4 jogos a 25% (faixa 20-30%) e houve 1 empate em 4. Casa e fora: 1 jogo por faixa, ficam de fora
    assert len(calibracao) == 1
    empate = calibracao.iloc[0]
    assert (empate["Resultado"], empate["Faixa"], empate["RotuloFaixa"]) == ("Empate", 2, "20-30%")
    assert (empate["ProbMedia"], empate["FreqObservada"], empate["Jogos"]) == (0.25, 0.25, 4)

def test_ordem_dos_jogos_dentro_da_jornada():
    previsoes = pd.DataFrame({"JogoID": ["b", "a", "c"], "Jornada": [1, 1, 2], "Data": ["2026-08-09", "2026-08-08", "2026-08-15"],
                              "Hora": ["18:00", "20:30", "18:00"], "EquipaCasa": ["Benfica", "Porto", "Porto"],
                              "EquipaFora": ["Porto", "Benfica", "Benfica"], "Estado": "TIMED", "Tipo": "Provisória",
                              "GolosCasa": None, "GolosFora": None, "Resultado": None, "FonteResultado": None})
    jogos = warehouse.dim_jogo(previsoes, warehouse.dim_equipa(equipas(), calendario())).set_index("JogoID")
    # Na jornada 1, o "a" (sábado) vem antes do "b" (domingo); a jornada 2 recomeça no 1
    assert jogos["OrdemJornada"].to_dict() == {"a": 1, "b": 2, "c": 1}


def test_estatisticas_dos_jogos_como_inteiros():
    jogos_epoca = pd.DataFrame({"JogoID": ["j1"], "Epoca": [cfg.EPOCA_ATUAL]}
                               | {coluna: [3.0] for coluna in cfg.COLUNAS_ESTATISTICAS})
    estatisticas = warehouse.fato_estatisticas_jogo(jogos_epoca)
    assert list(estatisticas.columns) == ["JogoID"] + cfg.COLUNAS_ESTATISTICAS
    assert estatisticas.loc[0, "RematesCasa"] == 3 and str(estatisticas["RematesCasa"].dtype) == "Int64"

def test_classificacao_final_das_epocas_anteriores():
    jogos = pd.DataFrame({"Epoca": ["2024-25"] * 2 + ["2025-26"] * 2,
                          "EquipaCasa": ["Benfica", "Porto", "Benfica", "Tondela"],
                          "EquipaFora": ["Porto", "Benfica", "Tondela", "Benfica"],
                          "GolosCasa": [2, 0, 1, 1], "GolosFora": [0, 0, 1, 3]})
    epocas = warehouse.fato_epocas_equipa(jogos, pd.DataFrame({"Equipa": ["Benfica", "Porto"]}))
    linhas = epocas.set_index(["Epoca", "Equipa"])
    # 2024-25: Benfica 4 pontos (1.º), Porto 1 (2.º). O Tondela não está nesta época: fica de fora
    assert linhas.loc[("2024-25", "Benfica"), ["Posicao", "Pontos"]].tolist() == [1, 4]
    assert linhas.loc[("2024-25", "Porto"), ["Posicao", "Pontos"]].tolist() == [2, 1]
    # 2025-26: o Porto não jogou (estava noutra divisão), por isso não tem linha
    assert ("2025-26", "Porto") not in linhas.index and len(epocas) == 3

# ---------------------------------------------------------------------
# Equipas e jogadores (fichas da ESPN)
# ---------------------------------------------------------------------
def espn_jogos():
    # Dois jogos do Benfica: ganha 2-0 ao Porto em casa (90') e perde 1-0 em Braga (90')
    return pd.DataFrame({"JogoID": ["j1", "j2"], "EquipaCasa": ["Benfica", "Braga"], "EquipaFora": ["Porto", "Benfica"],
                         "GolosCasa": [2, 1], "GolosFora": [0, 0], "Duracao": [90.0, 90.0]})


def jogador_jogo(jogo, evento, jogador, nome, equipa, linha, minutos, pro, contra, titular=1, **estatisticas):
    linha_tabela = {"JogoID": jogo, "EventoID": evento, "JogadorID": jogador, "Nome": nome, "Equipa": equipa,
                    "Linha": linha, "Titular": titular, "Minutos": minutos,
                    "GolosProEmCampo": pro, "GolosContraEmCampo": contra}
    return linha_tabela | {coluna: estatisticas.get(coluna, 0) for coluna in cfg.ESTATISTICAS_JOGADOR_ESPN.values()}


def jogadores_jogo():
    return pd.DataFrame([
        # Avançado: joga tudo nos dois jogos, marca os 2 golos
        jogador_jogo("j1", "10", "A", "Avançado", "Benfica", "AV", 90, 2, 0, Golos=2),
        jogador_jogo("j2", "20", "A", "Avançado", "Benfica", "AV", 90, 0, 1),
        # Guarda-redes: só joga o 1.º jogo, sem sofrer
        jogador_jogo("j1", "10", "G", "Guarda-redes", "Benfica", "GR", 90, 2, 0, Defesas=3),
        # Médio: entra aos 60' do 2.º jogo (30 minutos) e não apanha o golo
        jogador_jogo("j2", "20", "M", "Médio", "Benfica", "MED", 30, 0, 0, titular=0),
        # Suplente que nunca entrou e nunca teve posição
        jogador_jogo("j1", "10", "S", "Suplente", "Benfica", None, 0, 0, 0, titular=0)])


def test_posse_e_golos_de_cada_equipa():
    estatisticas = pd.DataFrame({"JogoID": ["j1", "j1"], "Equipa": ["Benfica", "Porto"]}
                                | {coluna: [55.0, 45.0] for coluna in cfg.ESTATISTICAS_EQUIPA_ESPN.values()})
    tabela = warehouse.fato_equipa_jogo(estatisticas, espn_jogos()).set_index("Equipa")
    assert (tabela.loc["Benfica", "Golos"], tabela.loc["Porto", "Golos"]) == (2, 0)
    assert tabela.loc["Benfica", "PosseBola"] == 55.0


def test_jogadores_linha_e_nomes_unicos():
    jogadores = jogadores_jogo()
    outro = jogador_jogo("j1", "10", "A2", "Avançado", "Porto", "AV", 90, 0, 2)   # mesmo nome, outro jogador
    dim = warehouse.dim_jogador(pd.concat([jogadores, pd.DataFrame([outro])])).set_index("JogadorID")
    assert dim.loc["S", "Linha"] == "S/P"
    assert {dim.loc["A", "Nome"], dim.loc["A2", "Nome"]} == {"Avançado (Benfica)", "Avançado (Porto)"}


def test_epoca_de_cada_jogador(monkeypatch):
    monkeypatch.setattr(cfg, "MINUTOS_MINIMOS_IMPACTO", 60)
    jogadores = jogadores_jogo()
    epoca = warehouse.fato_jogador_epoca(jogadores, espn_jogos(), warehouse.dim_jogador(jogadores)).set_index("JogadorID")
    # O Benfica jogou 180 minutos. Avançado: 180 (100%), Médio: 30 (17%), Suplente: 0
    assert epoca.loc["A", "Funcao"] == "Titular habitual" and epoca.loc["A", "Golos"] == 2
    assert epoca.loc["M", "Funcao"] == "Pouco utilizado" and epoca.loc["S", "Funcao"] == "Sem minutos"
    # Guarda-redes: 90 minutos sem sofrer -> 1 jogo sem sofrer; titular em 50% dos minutos -> rotação
    assert epoca.loc["G", "JogosSemSofrer"] == 1 and epoca.loc["G", "Funcao"] == "Rotação"
    # Impacto do guarda-redes: com ele +2 em 90' (+2 por 90); sem ele -1 em 90' (-1 por 90) -> +3
    assert (epoca.loc["G", "SaldoComEle90"], epoca.loc["G", "SaldoSemEle90"], epoca.loc["G", "Impacto90"]) == (2, -1, 3)
    # O avançado jogou tudo: sem ele são 0 minutos, por isso não há impacto
    assert pd.isna(epoca.loc["A", "Impacto90"])
    # Bolinhas: cada um na sua linha, o mais utilizado ao centro (X = 0)
    assert (epoca.loc["A", "PlantelY"], epoca.loc["G", "PlantelY"], epoca.loc["S", "PlantelY"]) == (5, 2, 1)
    assert epoca.loc["A", "PlantelX"] == 0


def test_bolinhas_espalhadas_a_partir_do_centro():
    assert warehouse.posicoes_no_plantel([900, 800, 700, 600, 500]) == [0, -1, 1, -2, 2]