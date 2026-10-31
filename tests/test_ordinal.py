"""
=====================================================================
 TESTES DA REGRESSÃO LOGÍSTICA ORDINAL
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

import configuracao as cfg
import func.ordinal as ordinal


def jogos_simulados(n=6000, semente=0):
    """Jogos gerados com um modelo ordinal conhecido: peso 1, cortes -0,8 e 0,4."""
    gerador = np.random.default_rng(semente)
    x = gerador.normal(size=n)
    u = gerador.random(n)
    ate_fora, ate_empate = expit(-0.8 - x), expit(0.4 - x)
    resultado = np.where(u < ate_fora, "A", np.where(u < ate_empate, "D", "H"))
    return pd.DataFrame({"Epoca": cfg.EPOCAS_ESPERADAS[1], "Forca": x, "Resultado": resultado})


def test_probabilidades_feitas_a_mao():
    # Força 0, corte1 = -1, corte2 = 1 (log da distância = log 2)
    # fora = sigmoide(-1) = 0,269; até empate = sigmoide(1) = 0,731
    p = ordinal.probabilidades(np.array([1.0, -1.0, np.log(2)]), np.array([[0.0]]))[0]
    assert p == pytest.approx([1 - 0.7311, 0.7311 - 0.2689, 0.2689], abs=1e-4)


def test_empate_mais_provavel_em_jogos_equilibrados():
    parametros = np.array([1.0, -1.0, np.log(2)])
    empate = ordinal.probabilidades(parametros, np.array([[-3.0], [0.0], [3.0]]))[:, 1]
    assert empate[1] > empate[0] and empate[1] > empate[2]


def test_recupera_os_numeros_verdadeiros():
    dados = jogos_simulados()
    parametros = ordinal.ajustar(dados[["Forca"]].to_numpy(), dados["Resultado"])
    assert parametros[0] == pytest.approx(1.0, abs=0.1)                       # peso
    assert parametros[1] == pytest.approx(-0.8, abs=0.1)                      # corte 1
    assert parametros[1] + np.exp(parametros[2]) == pytest.approx(0.4, abs=0.1)   # corte 2


def test_resultado_da_epoca_a_prever_nao_e_usado():
    dados = jogos_simulados()
    treino, teste = dados.iloc[:5000], dados.iloc[5000:]
    baralhado = teste.assign(Resultado=teste["Resultado"].sample(frac=1, random_state=1).to_numpy())
    previsor = ordinal.criar_previsor(["Forca"])
    assert previsor(treino, baralhado) == pytest.approx(previsor(treino, teste))