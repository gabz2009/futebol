"""
=====================================================================
 TESTES DAS PREVISÕES DA ÉPOCA ATUAL (MODO SEMANAL)
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest

import configuracao as cfg
import func.avaliacao as av
import func.boosting as gb
import func.previsao as previsao

EPOCA = cfg.EPOCAS_ESPERADAS[1]


def epoca_com_jogos_por_jogar():
    """3 semanas jogadas (2 jogos por semana) e 2 semanas por jogar."""
    datas = pd.to_datetime(["2018-08-04", "2018-08-05", "2018-08-11", "2018-08-12", "2018-08-18", "2018-08-19",
                            "2018-08-25", "2018-08-26", "2018-09-01", "2018-09-02"])
    return pd.DataFrame({"JogoID": [f"j{i}" for i in range(10)], "Epoca": EPOCA, "Data": datas,
                         "Resultado": ["H", "D", "A", "H", "D", "A", None, None, None, None]})


def test_cada_semana_treina_so_com_os_jogos_anteriores():
    treino = pd.DataFrame({"JogoID": ["antigo"], "Epoca": cfg.EPOCAS_ESPERADAS[0],
                           "Data": pd.to_datetime(["2018-05-01"]), "Resultado": ["H"]})
    chamadas = []

    def previsor_espiao(treino_semana, teste_semana):
        chamadas.append((sorted(treino_semana["JogoID"]), sorted(teste_semana["JogoID"])))
        # Devolve na 1.ª coluna o número de jogos de treino, para se ver qual treino cada jogo teve
        return np.column_stack([np.full(len(teste_semana), len(treino_semana)), np.zeros((len(teste_semana), 2))])

    p = previsao.semana_a_semana(previsor_espiao)(treino, epoca_com_jogos_por_jogar())
    # Semana 1: só o jogo antigo. Semana 2: + 2 jogos. Semana 3: + 4.
    # Semanas 4 e 5 (por jogar): + os 6 jogados, e juntas numa só chamada (o treino é igual)
    assert list(p[:, 0]) == [1, 1, 3, 3, 5, 5, 7, 7, 7, 7]
    assert len(chamadas) == 4
    assert chamadas[1] == (["antigo", "j0", "j1"], ["j2", "j3"])


def test_medidas_vazias_nos_jogos_por_jogar():
    m = av.medidas_por_jogo([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]], ["H", None])
    assert m.loc[0, "LogLoss"] == pytest.approx(-np.log(0.5))
    assert m.loc[1].isna().all()


def test_boosting_escolhe_os_parametros_uma_vez_por_epoca(monkeypatch):
    vezes = []
    monkeypatch.setattr(gb, "escolher_parametros",
                        lambda treino, colunas, grelha: vezes.append(1) or
                        {"learning_rate": 0.1, "max_depth": 1, "max_iter": 5, "min_samples_leaf": 1})
    dados = pd.DataFrame({"Epoca": EPOCA, "Forca": np.arange(30.0), "Resultado": ["H", "D", "A"] * 10})
    previsor = gb.criar_previsor(["Forca"])
    previsor(dados.iloc[:20], dados.iloc[20:25])
    previsor(dados.iloc[:25], dados.iloc[25:])          # semana seguinte da mesma época
    assert len(vezes) == 1



def test_tipo_de_cada_previsao():
    tabela = pd.DataFrame({
        "Jogado": [1, 0, 0, 0, 0, 0],
        "Estado": ["FINISHED", "FINISHED", "POSTPONED", "TIMED", "TIMED", "SCHEDULED"],
        "Jornada": [9, 9, 8, 10, 10, 11]})
    # O adiado da jornada 8 não conta como "próxima jornada": a próxima é a 10
    assert list(previsao.tipo_de_previsao(tabela)) == ["Jogado", "À espera de dados", "Provisória",
                                                       "Próxima jornada", "Próxima jornada", "Provisória"]

def test_fonte_do_resultado_csv_ou_api():
    # j1 está no CSV; j2 já acabou mas só está na API (0-2); j3 por jogar
    final = pd.DataFrame({"JogoID": ["j1", "j2", "j3"], "Epoca": EPOCA, "Resultado": ["H", "A", None],
                          "ProbH": 0.5, "ProbD": 0.3, "ProbA": 0.2})
    final = pd.concat([final, av.medidas_por_jogo(final[["ProbH", "ProbD", "ProbA"]], final["Resultado"])], axis=1)
    calendario = pd.DataFrame({"JogoID": ["j1", "j2", "j3"], "Jornada": [1, 1, 2], "Data": "2026-08-08",
                               "Hora": "20:00", "EquipaCasa": "A", "EquipaFora": "B",
                               "Estado": ["FINISHED", "FINISHED", "TIMED"]})
    variaveis = pd.DataFrame({"JogoID": ["j1", "j2", "j3"]}).assign(
        **{c: np.nan for c in ["ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora",
                               "ProbOddsFechoCasa", "ProbOddsFechoEmpate", "ProbOddsFechoFora"]})
    jogos = pd.DataFrame({"JogoID": ["j1", "j2"], "GolosCasa": [2, 0], "GolosFora": [1, 2],
                          "Ficheiro": ["P1_2026-27.csv", "API"]})
    tabela = previsao.tabela_previsoes({"Modelo final": final}, calendario, variaveis, jogos).set_index("JogoID")
    assert tabela.loc["j2", ["FonteResultado", "Tipo", "GolosFora"]].tolist() == ["API", "Jogado", 2]
    assert tabela.loc["j2", "LogLoss"] == pytest.approx(-np.log(0.2))         # o modelo sabe se acertou
    assert tabela.loc["j1", "FonteResultado"] == "CSV"
    assert pd.isna(tabela.loc["j3", "FonteResultado"]) and tabela.loc["j3", "Tipo"] == "Próxima jornada"


def test_previsoes_reais_a_partir_da_data_de_inicio():
    # j1 antes do início (reconstruída), j2 depois (real, já jogado), j3 real por jogar
    oficiais = pd.DataFrame({"Epoca": EPOCA, "Jornada": [9, 10, 10], "JogoID": ["j1", "j2", "j3"],
                             "DataCorte": ["2026-10-23", "2026-10-30", "2026-10-30"],
                             "ProbCasa": 0.5, "ProbEmpate": 0.3, "ProbFora": 0.2, "Previsto": "H"})
    tabela = pd.DataFrame({"JogoID": ["j1", "j2", "j3"], "Data": ["2026-10-25", cfg.INICIO_PREVISOES_REAIS, "2026-11-09"],
                           "Hora": "20:00", "EquipaCasa": "A", "EquipaFora": "B", "Resultado": ["H", "A", None],
                           "FonteResultado": ["CSV", "API", None], "ProbOddsCasa": np.nan,
                           "ProbOddsEmpate": np.nan, "ProbOddsFora": np.nan})
    avaliacao = previsao.avaliar_oficiais(oficiais, tabela).set_index("JogoID")
    assert avaliacao.index.tolist() == ["j2", "j3"]        # só os jogos a partir de cfg.INICIO_PREVISOES_REAIS
    assert avaliacao.loc["j2", ["Acerto", "FonteResultado"]].tolist() == [0.0, "API"]
    assert avaliacao.loc["j2", "LogLoss"] == pytest.approx(-np.log(0.2))
    assert pd.isna(avaliacao.loc["j3", "Acerto"])

def test_tipo_de_cada_previsao():
    tabela = pd.DataFrame({
        "Jogado": [1, 0, 0, 0, 0, 0, 0],
        "Estado": ["FINISHED", "FINISHED", "POSTPONED", "TIMED", "TIMED", "SCHEDULED", "TIMED"],
        "Jornada": [9, 9, 8, 10, 10, 11, 9],
        "Data": ["2026-10-25", "2026-10-26", "2026-10-18", "2026-11-01", "2026-11-02", "2026-11-08", "2026-11-05"]})
    # O adiado da jornada 8 (sem data nova) não conta como "próxima jornada": a próxima é a 10.
    # O último jogo é da jornada 9 mas foi remarcado para 05/11, depois do início da 10: também não conta
    assert list(previsao.tipo_de_previsao(tabela)) == ["Jogado", "À espera de dados", "Adiado", "Próxima jornada",
                                                       "Próxima jornada", "Provisória", "Remarcado"]