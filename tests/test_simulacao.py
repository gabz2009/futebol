"""
=====================================================================
 TESTES DA SIMULAÇÃO DA ÉPOCA
=====================================================================
 Liga inventada com 4 equipas, onde se sabe a resposta certa:
   Terminados: A 1-0 B, B 5-0 C.   Por jogar: C - D (empate certo).
   Fim: A 3 pts, B 3 pts, C 1 pt, D 1 pt.
   - A à frente de B: ganhou o confronto direto (apesar de pior diferença de golos)
   - D à frente de C: empataram entre si; D tem melhor diferença de golos (0 contra -5)
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest

import func.simulacao as simulacao


def liga(prob_casa=0.0, prob_empate=1.0):
    return pd.DataFrame({
        "JogoID": ["ab", "bc", "cd"], "EquipaCasa": ["A", "B", "C"], "EquipaFora": ["B", "C", "D"],
        "GolosCasa": [1, 5, np.nan], "GolosFora": [0, 0, np.nan], "Terminado": [True, True, False],
        "ProbCasa": prob_casa, "ProbEmpate": prob_empate, "ProbFora": 1 - prob_casa - prob_empate})


def test_classificacao_atual_com_desempates():
    tabela = simulacao.classificacao_atual(liga()).set_index("Equipa")
    assert tabela.loc[["A", "B", "C", "D"], "Pontos"].tolist() == [3, 3, 0, 0]
    assert tabela.loc[["A", "B", "D", "C"], "Posicao"].tolist() == [1, 2, 3, 4]     # A ganhou a B; D tem melhor dif.
    assert tabela.loc["B", "DiferencaGolos"] == 4


def test_simulacao_com_resultado_certo():
    equipas, pontos, posicoes = simulacao.simular(liga(), simulacoes=50, semente=1)
    final = dict(zip(equipas, posicoes[0]))
    assert (posicoes == posicoes[0]).all()                     # o resultado é certo: todas as simulações iguais
    assert final == {"A": 1, "B": 2, "D": 3, "C": 4}
    assert dict(zip(equipas, pontos[0])) == {"A": 3, "B": 3, "C": 1, "D": 1}


def test_probabilidades_e_mesma_semente_mesmo_resultado():
    jogos = liga(prob_casa=0.5, prob_empate=0.3)
    equipas, pontos, posicoes = simulacao.simular(jogos, simulacoes=4000, semente=7)
    resumo = simulacao.resumir(equipas, pontos, posicoes, simulacao.classificacao_atual(jogos)).set_index("Equipa")
    # C ganha 50% das vezes (3 pontos) e empata 30% (1 ponto): 0,5 x 3 + 0,3 x 1 = 1,8 pontos esperados
    assert resumo.loc["C", "PontosEsperados"] == pytest.approx(0.5 * 3 + 0.3 * 1, abs=0.1)
    por_posicao = simulacao.probabilidades_por_posicao(equipas, posicoes)
    assert np.allclose(por_posicao.groupby("Equipa")["Probabilidade"].sum(), 1)
    assert np.allclose(por_posicao.groupby("Posicao")["Probabilidade"].sum(), 1)
    _, _, outra_vez = simulacao.simular(jogos, simulacoes=4000, semente=7)
    assert (outra_vez == posicoes).all()

def test_classificacao_depois_de_cada_jornada():
    jogos = liga().assign(Jornada=[1, 2, 2])
    tabela = simulacao.classificacao_por_jornada(jogos).set_index(["Jornada", "Equipa"])
    assert tabela.loc[(1, "A"), "Pontos"] == 3 and tabela.loc[(1, "B"), "Pontos"] == 0    # só A-B na jornada 1
    assert tabela.loc[(2, "B"), "Pontos"] == 3                                            # B ganhou na jornada 2
    assert sorted(tabela.index.get_level_values("Jornada").unique()) == [1, 2]  