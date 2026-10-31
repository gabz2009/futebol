"""
=====================================================================
 GRADIENT BOOSTING (árvores de decisão em sequência)
=====================================================================
 A IDEIA
   Começa-se com uma previsão igual para todos os jogos (as frequências
   de casa / empate / fora). Depois junta-se uma árvore pequena que
   corrige os maiores erros, outra que corrige os erros que sobraram,
   e assim por diante. Cada árvore só corrige uma parte (learning_rate),
   para o modelo não decorar os jogos de treino.

 PORQUE É PRECISO AFINAR COM CUIDADO
   Temos poucos jogos (918 a 1836 de treino por ronda). Com árvores a
   mais ou demasiado fundas, o modelo decora o treino e piora nos jogos
   novos. Os parâmetros são escolhidos de novo em cada ronda do
   walk-forward, porque o tamanho do treino muda de ronda para ronda.

 COMO SE ESCOLHEM OS PARÂMETROS (SEM VER A ÉPOCA A PREVER)
   Dentro do treino de cada ronda, para cada combinação da grelha:
     - prevê-se cada uma das últimas cfg.GB_EPOCAS_AFINACAO épocas
       com um modelo treinado só nas épocas anteriores a ela;
     - calcula-se o log loss médio.
   Fica a combinação com menor log loss. Depois treina-se com o treino
   todo e prevê-se a época da ronda.
=====================================================================
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import ParameterGrid

import configuracao as cfg
import func.avaliacao as av


def criar_modelo(parametros):
    # early_stopping=False: sem isto, o scikit-learn guardava parte do treino à sorte
    return HistGradientBoostingClassifier(early_stopping=False, random_state=0, **parametros)


def erros_por_arvores(treino, colunas, parametros, numeros_arvores):
    """Log loss médio nas últimas épocas do treino (cada uma prevista só com as
    anteriores), para cada número de árvores de 'numeros_arvores'.
    Basta UM ajuste por época: o modelo com 200 árvores passa, pelo caminho,
    pelos modelos com 10, 25, 50 e 100 (staged_predict_proba dá a previsão
    depois de cada árvore)."""
    epocas = sorted(treino["Epoca"].unique())[-cfg.GB_EPOCAS_AFINACAO:]
    erros = {n: [] for n in numeros_arvores}
    for epoca in epocas:
        antes, durante = treino[treino["Epoca"] < epoca], treino[treino["Epoca"] == epoca]
        modelo = criar_modelo({**parametros, "max_iter": max(numeros_arvores)}).fit(antes[colunas], antes["Resultado"])
        ordem = [list(modelo.classes_).index(r) for r in cfg.RESULTADOS_VALIDOS]     # H, D, A
        for n, probabilidades in enumerate(modelo.staged_predict_proba(durante[colunas]), start=1):
            if n in erros:
                erros[n].append(av.medidas_por_jogo(probabilidades[:, ordem], durante["Resultado"])["LogLoss"].mean())
    return {n: np.mean(e) for n, e in erros.items()}


def escolher_parametros(treino, colunas, grelha):
    """A combinação da grelha com menor log loss nas últimas épocas do treino."""
    sem_arvores = {nome: valores for nome, valores in grelha.items() if nome != "max_iter"}
    candidatos = []
    for parametros in ParameterGrid(sem_arvores):
        for n, erro in erros_por_arvores(treino, colunas, parametros, grelha["max_iter"]).items():
            candidatos.append((erro, {**parametros, "max_iter": n}))
    return min(candidatos, key=lambda candidato: candidato[0])[1]


def criar_previsor(colunas, grelha=cfg.GB_GRELHA):
    """Devolve um previsor(treino, teste) para o avaliacao.walk_forward.
    Os parâmetros escolhidos em cada ronda ficam em previsor.escolhidos."""
    def previsor(treino, teste):
        epoca = teste["Epoca"].iloc[0]
        if epoca not in previsor.escolhidos:
            previsor.escolhidos[epoca] = escolher_parametros(treino, colunas, grelha)
        modelo = criar_modelo(previsor.escolhidos[epoca]).fit(treino[colunas], treino["Resultado"])
        return av.prever(modelo, teste[colunas])

    previsor.escolhidos = {}
    return previsor