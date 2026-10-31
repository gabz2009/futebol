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