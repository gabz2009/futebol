"""
=====================================================================
 REGRESSÃO LOGÍSTICA ORDINAL (o modelo do artigo dos GAP ratings)
=====================================================================
 PORQUE "ORDINAL"
   Os resultados têm uma ordem: fora < empate < casa. A regressão
   logística normal (multinomial) não sabe isto: trata os três como
   categorias soltas e precisa de um conjunto de pesos para cada uma.
   A ordinal usa a ordem: há UMA só "força do jogo" e dois cortes.

 COMO FUNCIONA
   1. Força do jogo: s = b1 x GapFalhadosDif + b2 x GapBalizaDif + ...
      (s alto = a casa é muito melhor)
   2. Dois cortes, c1 < c2, dividem a força em três zonas:
        P(fora)   = sigmoide(c1 - s)
        P(empate) = sigmoide(c2 - s) - sigmoide(c1 - s)
        P(casa)   = 1 - sigmoide(c2 - s)
   O empate fica naturalmente no meio: é mais provável quando as
   equipas estão equilibradas (s perto do meio dos cortes) e menos
   quando uma é muito melhor. Por isso não precisa de EquilibrioElo.

 MENOS NÚMEROS PARA ESTIMAR
   Com 3 variáveis: 3 pesos + 2 cortes = 5 números (a multinomial
   com 4 variáveis estima 15). Menos números = menos risco de
   aprender a sorte do treino.

 FONTE
   Wheatcroft (2020/2021) usa a regressão logística ordinal com os
   GAP ratings, tal como aqui.
=====================================================================
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit           # sigmoide: 1 / (1 + e^-x)

import configuracao as cfg

POSICAO = {resultado: i for i, resultado in enumerate(cfg.RESULTADOS_VALIDOS)}     # H=0, D=1, A=2


def probabilidades(parametros, X):
    """Probabilidades H, D, A. 'parametros' = pesos + corte 1 + log(distância entre cortes)."""
    forca = X @ parametros[:-2]
    corte1 = parametros[-2]
    corte2 = corte1 + np.exp(parametros[-1])        # exp garante que corte2 > corte1
    ate_fora, ate_empate = expit(corte1 - forca), expit(corte2 - forca)
    return np.column_stack([1 - ate_empate, ate_empate - ate_fora, ate_fora])


def ajustar(X, resultados):
    """Escolhe os pesos e os cortes que dão maior probabilidade aos resultados do treino."""
    y = np.array([POSICAO[r] for r in resultados])

    def custo(parametros):
        p = probabilidades(parametros, X)[np.arange(len(y)), y]
        return -np.log(np.clip(p, 1e-12, 1)).sum()

    inicio = np.concatenate([np.zeros(X.shape[1]), [-0.5, 0.0]])
    return minimize(custo, inicio, method="BFGS").x


def criar_previsor(colunas):
    """Devolve um previsor(treino, teste) para o avaliacao.walk_forward.
    As variáveis são padronizadas com a média e o desvio do TREINO."""
    def previsor(treino, teste):
        media, desvio = treino[colunas].mean(), treino[colunas].std()
        parametros = ajustar(((treino[colunas] - media) / desvio).to_numpy(), treino["Resultado"])
        return probabilidades(parametros, ((teste[colunas] - media) / desvio).to_numpy())

    return previsor