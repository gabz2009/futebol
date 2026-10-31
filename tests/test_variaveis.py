"""
=====================================================================
 TESTES DAS VARIÁVEIS (FASE 2)
=====================================================================
 Usam uma mini-liga inventada, com poucos jogos, para se conseguir
 confirmar as contas à mão.
=====================================================================
"""
import pandas as pd
import pytest
import numpy as np

import configuracao as cfg
import func.elo as elo
import func.variaveis as variaveis_mod
import func.pi_ratings as pi_ratings
import func.gap_ratings as gap_ratings

EPOCA = cfg.EPOCAS_ESPERADAS[0]       # primeira época dos dados, no formato da configuração


def mini_liga():
    """A joga 3 vezes em casa contra B, C e D e marca 1, 2 e 3 golos."""
    jogos = pd.DataFrame({
        "JogoID": ["j1", "j2", "j3"],
        "Epoca": EPOCA,
        "Data": pd.to_datetime(["2017-08-06", "2017-08-13", "2017-08-20"]),
        "Hora": None,
        "EquipaCasa": ["A", "A", "A"],
        "EquipaFora": ["B", "C", "D"],
        "GolosCasa": [1, 2, 3], "GolosFora": [0, 2, 4],
        "Resultado": ["H", "D", "A"],
        "RematesBalizaCasa": [3, 4, 5], "RematesBalizaFora": [1, 2, 6],
        "OddCasaB365": 2.0, "OddEmpateB365": 3.4, "OddForaB365": 3.8,
        "OddCasaMedia": 2.0, "OddEmpateMedia": 3.4, "OddForaMedia": 3.8,
        "EpocaCOVID": False,
    })
    epocas = pd.DataFrame({"Epoca": [EPOCA], "Uso": ["Aquecimento"]})
    return completar_colunas(jogos), epocas

def completar_colunas(jogos):
    """Acrescenta as colunas que o teste não precisa de definir (odds de fecho vazias, etc.)."""
    jogos = jogos.copy()
    padrao = {"Hora": None, "RematesBalizaCasa": 4, "RematesBalizaFora": 3,
              "RematesCasa": 10, "RematesFora": 8, "CantosCasa": 5, "CantosFora": 4,
              "OddCasaB365": 2.0, "OddEmpateB365": 3.4, "OddForaB365": 3.8,
              "OddCasaMedia": 2.0, "OddEmpateMedia": 3.4, "OddForaMedia": 3.8,
              "EpocaCOVID": False}
    for coluna, valor in padrao.items():
        if coluna not in jogos:
            jogos[coluna] = valor
    for coluna in cfg.COLUNAS_ODDS_FECHO:
        if coluna not in jogos:
            jogos[coluna] = float("nan")
    if "Resultado" not in jogos:
        diferenca = jogos["GolosCasa"] - jogos["GolosFora"]
        jogos["Resultado"] = ["H" if d > 0 else "A" if d < 0 else "D" for d in diferenca]
    return jogos


def tres_epocas():
    """X joga a 1.ª época, desce, e volta na 3.ª. C sobe na 2.ª e desce logo.
    Época 1: A, B, X | Época 2: A, B, C | Época 3: A, B, X"""
    e1, e2, e3 = cfg.EPOCAS_ESPERADAS[0], cfg.EPOCAS_ESPERADAS[1], cfg.EPOCAS_ESPERADAS[2]
    linhas = [
        (e1, "2017-08-06", "A", "B", 1, 0), (e1, "2017-08-13", "X", "A", 4, 0), (e1, "2017-08-20", "B", "X", 0, 4),
        (e2, "2018-08-06", "A", "B", 1, 1), (e2, "2018-08-13", "C", "A", 1, 1), (e2, "2018-08-20", "B", "C", 1, 1),
        (e3, "2019-08-06", "X", "B", 0, 0), (e3, "2019-08-13", "A", "X", 1, 0),
    ]
    jogos = pd.DataFrame(linhas, columns=["Epoca", "Data", "EquipaCasa", "EquipaFora", "GolosCasa", "GolosFora"])
    jogos["Data"] = pd.to_datetime(jogos["Data"])
    jogos.insert(0, "JogoID", [f"j{i}" for i in range(1, len(jogos) + 1)])
    epocas = pd.DataFrame({"Epoca": [e1, e2, e3], "Uso": ["Aquecimento", "Treino", "Treino"]})
    return completar_colunas(jogos), epocas


def test_media_usa_so_os_jogos_anteriores():
    jogos, epocas = mini_liga()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos), gap_ratings.calcular_gap(jogos), epocas).set_index("JogoID")
    coluna = f"CasaGolosMarcadosUlt{cfg.JANELA_FORMA}"
    assert pd.isna(v.loc["j1", coluna])          # 1.º jogo: ainda não há jogos anteriores
    assert v.loc["j2", coluna] == 1              # só o j1
    assert v.loc["j3", coluna] == 1.5            # média de j1 e j2, nunca o próprio j3


def test_pontos_contam_vitoria_empate_derrota():
    jogos, epocas = mini_liga()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos), gap_ratings.calcular_gap(jogos), epocas).set_index("JogoID")
    # Antes do j3, A tinha uma vitória (3) e um empate (1): média 2
    assert v.loc["j3", f"CasaPontosUlt{cfg.JANELA_FORMA}"] == 2


def test_elo_antes_do_jogo_e_atualizacao():
    jogos, _ = mini_liga()
    resultado = elo.calcular_elo(jogos).set_index("JogoID")
    # Primeiro jogo: as duas equipas começam com o Elo inicial
    assert resultado.loc["j1", "EloCasa"] == cfg.ELO_INICIAL
    # A ganhou o j1: o Elo dela no j2 sobe exatamente K x (1 - esperado)
    esperado = elo.probabilidade_esperada(cfg.ELO_INICIAL, cfg.ELO_INICIAL)
    assert resultado.loc["j2", "EloCasa"] == pytest.approx(cfg.ELO_INICIAL + cfg.ELO_K * (1 - esperado))


def test_probabilidades_das_odds_somam_1():
    jogos, _ = mini_liga()
    prob = variaveis_mod.probabilidades_odds(jogos)
    soma = prob[["ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]].sum(axis=1)
    assert soma.round(9).eq(1).all()

def test_margem_tirada_pelo_metodo_da_potencia():
    # Odds 2,0 / 3,4 / 3,8 -> inversos 0,500 / 0,294 / 0,263 (somam 1,057)
    inversos = np.array([1 / 2.0, 1 / 3.4, 1 / 3.8])
    p = variaveis_mod.remover_margem(inversos)
    assert p.sum() == pytest.approx(1)
    # Todas elevadas ao MESMO expoente k
    k = np.log(p) / np.log(inversos)
    assert k == pytest.approx(np.full(3, k[0]))
    # Comparado com dividir pela soma: o favorito fica com mais, o azarão com menos
    simples = inversos / inversos.sum()
    assert p[0] > simples[0] and p[2] < simples[2]

def test_pi_ratings_exemplo_de_dois_jogos():
    """O exemplo explicado à mão: A 2-0 B e depois B 1-1 A."""
    jogos = pd.DataFrame({
        "JogoID": ["j1", "j2"], "Epoca": EPOCA,
        "Data": pd.to_datetime(["2017-08-06", "2017-08-13"]), "Hora": None,
        "EquipaCasa": ["A", "B"], "EquipaFora": ["B", "A"],
        "GolosCasa": [2, 1], "GolosFora": [0, 1],
    })
    pi = pi_ratings.calcular_pi_ratings(jogos).set_index("JogoID")
    # Antes do 1.º jogo, todos a 0
    assert pi.loc["j1", "PiCasa"] == 0 and pi.loc["j1", "PiFora"] == 0
    # Antes do 2.º jogo: B em casa desceu 70% de 0,050 e A fora subiu o mesmo
    assert pi.loc["j2", "PiCasa"] == pytest.approx(-0.0351, abs=1e-4)
    assert pi.loc["j2", "PiFora"] == pytest.approx(0.0351, abs=1e-4)
    # A diferença esperada no 2.º jogo favorece ligeiramente A (fora)
    assert pi.loc["j2", "PiDifEsperada"] == pytest.approx(-0.0546, abs=1e-4)


def test_equipa_que_volta_e_promovida_e_recomeca_o_historico():
    jogos, epocas = tres_epocas()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos), gap_ratings.calcular_gap(jogos), epocas)
    v = v.set_index("JogoID")
    coluna = f"CasaGolosMarcadosUlt{cfg.JANELA_FORMA}"
    # j7: X volta na 3.ª época e joga em casa
    assert v.loc["j7", "CasaPromovida"] == 1
    # Não usa os 4 golos por jogo de X na 1.ª época (bloco antigo):
    # usa a média de golos de C, que desceu na 2.ª época (1 golo por jogo)
    assert v.loc["j7", coluna] == 1


def test_promovida_entra_com_o_elo_das_que_desceram():
    jogos, _ = tres_epocas()
    resultado = elo.calcular_elo(jogos).set_index("JogoID")
    # j5 é o 1.º jogo de C (promovida na 2.ª época). C entra com o Elo de X,
    # a única que desceu. X ganhou os 2 jogos que fez, por isso tinha Elo acima de 1500,
    # e C, apesar de nunca ter jogado, também começa acima de 1500.
    assert resultado.loc["j5", "EloCasa"] > cfg.ELO_INICIAL

def test_gap_exemplo_de_dois_jogos():
    """O exemplo explicado à mão, com lambda = 0,5 e phi1 = phi2 = 0,5.
    Jogo 1: A (casa) faz 10, B (fora) faz 4. Jogo 2: B recebe A."""
    jogos = pd.DataFrame({
        "Epoca": [EPOCA, EPOCA], "EquipaCasa": ["A", "B"], "EquipaFora": ["B", "A"],
        "ContagemCasa": [10, 0], "ContagemFora": [4, 0],
    })
    casa, fora = gap_ratings.esperado_por_jogo(jogos, "ContagemCasa", "ContagemFora", 0.5, 0.5, 0.5)
    # Jogo 1: tudo a 0, por isso o esperado é 0 para as duas
    assert casa[0] == 0 and fora[0] == 0
    # Depois do jogo 1 (cada rating muda 0,5 x 0,5 x erro):
    #   A: ataque em casa 2,5, ataque fora 2,5, defesa em casa 1, defesa fora 1
    #   B: ataque fora 1, ataque em casa 1, defesa fora 2,5, defesa em casa 2,5
    # Jogo 2 (B em casa): esperado de B = (ataque em casa B + defesa fora A) / 2 = (1 + 1) / 2
    assert casa[1] == pytest.approx(1.0)
    # esperado de A = (ataque fora A + defesa em casa B) / 2 = (2,5 + 2,5) / 2
    assert fora[1] == pytest.approx(2.5)


def com_jogos_por_jogar():
    """A mini-liga (3 jogos de A em casa) + 6 jogos de A em casa ainda por jogar.
    6 é mais do que a janela da forma (5): assim o último jogo por jogar só tem jogos
    por jogar na janela, e confirma-se que a forma não fica vazia."""
    jogos, epocas = mini_liga()
    futuros = pd.DataFrame({"JogoID": [f"f{i}" for i in range(1, 7)], "Epoca": EPOCA, "Hora": None,
                            "EpocaCOVID": False, "Data": pd.date_range("2017-08-27", periods=6, freq="7D"),
                            "EquipaCasa": "A", "EquipaFora": ["B", "C", "D"] * 2}).reindex(columns=jogos.columns)
    return pd.concat([jogos, futuros], ignore_index=True), epocas


def test_jogos_por_jogar_ficam_com_o_elo_de_hoje():
    jogos, _ = com_jogos_por_jogar()
    resultado = elo.calcular_elo(jogos).set_index("JogoID")
    # A perdeu o j3: o Elo de hoje é o de antes do j3 menos K x esperado
    antes = resultado.loc["j3"]
    hoje = antes["EloCasa"] - cfg.ELO_K * elo.probabilidade_esperada(antes["EloCasa"], antes["EloFora"])
    assert resultado.loc["f1", "EloCasa"] == pytest.approx(hoje)
    assert resultado.loc["f2", "EloCasa"] == pytest.approx(hoje)       # nada aconteceu entre f1 e f2


def test_jogos_por_jogar_forma_dos_ultimos_jogos_jogados():
    jogos, epocas = com_jogos_por_jogar()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos),
                                      gap_ratings.calcular_gap(jogos), epocas).set_index("JogoID")
    # A marcou 1, 2 e 3 golos nos 3 jogos jogados: média 2 nos jogos por jogar
    assert v.loc["f1", "CasaGolosMarcadosUlt5"] == pytest.approx(2)
    assert v.loc["f6", "CasaGolosMarcadosUlt5"] == pytest.approx(2)
    # Pi e GAP: preenchidos e iguais (não há resultado para os atualizar)
    assert v.loc["f1", "PiCasa"] == pytest.approx(v.loc["f6", "PiCasa"])
    assert v.loc[["f1", "f6"], ["PiCasa", "GapBalizaCasa"]].notna().all().all()
    assert v.loc[["f1", "f6"], "Resultado"].isna().all()


def test_jogo_por_jogar_com_data_passada_passa_para_depois_do_ultimo_jogo():
    import func.calendario as calendario_mod
    jogos, _ = mini_liga()
    calendario = pd.DataFrame({"JogoID": ["j1", "f1", "f2"], "Epoca": EPOCA,
                               "Data": ["2017-08-06", "2017-08-10", "2017-09-03"], "Hora": "20:00",
                               "EquipaCasa": "A", "EquipaFora": ["B", "B", "C"]})
    futuros = calendario_mod.jogos_por_jogar(calendario, jogos).set_index("JogoID")
    assert list(futuros.index) == ["f1", "f2"]                               # o j1 já foi jogado
    assert futuros.loc["f1", "Data"] == pd.Timestamp("2017-08-21")         # adiado: dia a seguir ao último (20/08)
    assert futuros.loc["f2", "Data"] == pd.Timestamp("2017-09-03")         # data futura fica igual
    assert futuros[["GolosCasa", "Resultado"]].isna().all().all()