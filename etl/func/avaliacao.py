"""
=====================================================================
 AVALIAÇÃO DOS MODELOS (FASE 5)
=====================================================================
 MEDIDAS (para cada jogo, depois média)
   - Acerto: o resultado com maior probabilidade aconteceu?
   - Log loss: -log(probabilidade dada ao que aconteceu). Medida
     principal. Adivinhar ao calhas (1/3 a cada) dá 1,099.
   - Brier: soma dos quadrados entre as probabilidades e o que
     aconteceu (1 no real, 0 nos outros).
   - RPS (Ranked Probability Score): como o Brier, mas usa a ordem
     casa > empate > fora. É a medida padrão nos estudos de previsão
     de futebol, por isso permite comparar com eles.
       RPS = 1/2 x [ (pH - rH)^2 + (pH + pD - rH - rD)^2 ]
   Em todas, exceto o acerto, quanto mais baixo melhor.

 VALIDAÇÃO "WALK-FORWARD" (em várias épocas, sempre para a frente)
   Para cada época de validação:
     treina com TODAS as épocas anteriores (sem o aquecimento)
     e prevê essa época.
   Ex.: valida 2021-22 treinando com 2018-19 a 2020-21;
        valida 2022-23 treinando com 2018-19 a 2021-22; ...
   É o uso real: prever sempre a época seguinte com o que veio antes.

 A ORDEM DAS COLUNAS DE PROBABILIDADES É SEMPRE H, D, A.
   (O scikit-learn usa A, D, H, por ordem alfabética: ver prever.)
=====================================================================
"""
import numpy as np
import pandas as pd

import configuracao as cfg


def resultado_em_01(resultado_real):
    """H, D, A -> tabela com 1 no resultado que aconteceu e 0 nos outros."""
    real = np.asarray(resultado_real)
    return np.column_stack([(real == r).astype(float) for r in cfg.RESULTADOS_VALIDOS])


def medidas_por_jogo(probabilidades, resultado_real):
    """Devolve uma tabela com as 4 medidas de cada jogo."""
    p = np.asarray(probabilidades, dtype=float)
    r = resultado_em_01(resultado_real)
    prob_do_real = (p * r).sum(axis=1)
    previsto = np.array(cfg.RESULTADOS_VALIDOS)[p.argmax(axis=1)]
    acumulada_p, acumulada_r = np.cumsum(p, axis=1), np.cumsum(r, axis=1)
    return pd.DataFrame({
        "Acerto": (previsto == np.asarray(resultado_real)).astype(float),
        "LogLoss": -np.log(np.clip(prob_do_real, 1e-15, 1)),
        "Brier": ((p - r) ** 2).sum(axis=1),
        # Só as 2 primeiras diferenças acumuladas: a 3.ª é sempre 0 (as duas somam 1)
        "RPS": ((acumulada_p[:, :2] - acumulada_r[:, :2]) ** 2).sum(axis=1) / 2,
    })


def prever(modelo, X):
    """Probabilidades de um modelo do scikit-learn na ordem H, D, A."""
    return pd.DataFrame(modelo.predict_proba(X), columns=modelo.classes_)[cfg.RESULTADOS_VALIDOS].to_numpy()


def walk_forward(variaveis, previsor, uso="Validação"):
    """Corre a validação walk-forward.
    previsor(treino, teste) -> probabilidades (H, D, A) para os jogos de 'teste'.
    Devolve uma tabela com uma linha por jogo de validação: época e as 4 medidas."""
    epocas = sorted(variaveis.loc[variaveis["Uso"] == uso, "Epoca"].unique())
    usaveis = variaveis[variaveis["Uso"] != "Aquecimento"]
    partes = []
    for epoca in epocas:
        treino = usaveis[usaveis["Epoca"] < epoca]
        teste = usaveis[usaveis["Epoca"] == epoca]
        probabilidades = np.asarray(previsor(treino, teste), dtype=float)
        medidas = medidas_por_jogo(probabilidades, teste["Resultado"])
        medidas.insert(0, "JogoID", teste["JogoID"].to_numpy())
        medidas.insert(1, "Epoca", epoca)
        medidas.insert(2, "Resultado", teste["Resultado"].to_numpy())
        # Guardam-se as probabilidades para a calibração
        for coluna, resultado in zip(probabilidades.T, cfg.RESULTADOS_VALIDOS):
            medidas[f"Prob{resultado}"] = coluna
        partes.append(medidas)
    return pd.concat(partes, ignore_index=True)

def media_geometrica(lista_resultados):
    """Combina vários modelos (tabelas do walk_forward) num só.
    Em cada jogo: multiplica as probabilidades dos modelos, tira a raiz
    (raiz quadrada com 2 modelos, cúbica com 3) e volta a pôr a somar 1.
    Pesos iguais: não há nada para afinar, por isso não se escolhe a olhar
    para a validação. Devolve uma tabela no mesmo formato do walk_forward."""
    primeira = lista_resultados[0]
    for outra in lista_resultados[1:]:
        if not (outra["JogoID"].to_numpy() == primeira["JogoID"].to_numpy()).all():
            raise ValueError("As tabelas não têm os mesmos jogos pela mesma ordem")
    colunas = [f"Prob{r}" for r in cfg.RESULTADOS_VALIDOS]
    logs = np.mean([np.log(r[colunas].to_numpy()) for r in lista_resultados], axis=0)
    probabilidades = np.exp(logs)
    probabilidades = probabilidades / probabilidades.sum(axis=1, keepdims=True)

    combinada = medidas_por_jogo(probabilidades, primeira["Resultado"])
    combinada.insert(0, "JogoID", primeira["JogoID"].to_numpy())
    combinada.insert(1, "Epoca", primeira["Epoca"].to_numpy())
    combinada.insert(2, "Resultado", primeira["Resultado"].to_numpy())
    for coluna, valores in zip(colunas, probabilidades.T):
        combinada[coluna] = valores
    return combinada

def resumo(resultados_por_modelo):
    """{nome: tabela do walk_forward} -> média de cada medida e log loss por época."""
    linhas = []
    for nome, r in resultados_por_modelo.items():
        linha = {"Modelo": nome}
        linha.update(r[["Acerto", "LogLoss", "Brier", "RPS"]].mean().round(4).to_dict())
        linha["ECE"] = ece_por_resultado(r)["Média"]
        for epoca, valor in r.groupby("Epoca")["LogLoss"].mean().items():
            linha[f"LL {epoca}"] = round(valor, 4)
        linhas.append(linha)
    return pd.DataFrame(linhas).sort_values("LogLoss").reset_index(drop=True)


def comparar(resultados_a, resultados_b, sorteios=2000, semente=42):
    """Bootstrap da diferença de log loss (A - B) jogo a jogo.
    Negativo = A melhor. Devolve a diferença média e o intervalo de 95%."""
    diferenca = (resultados_a["LogLoss"].to_numpy() - resultados_b["LogLoss"].to_numpy())
    gerador = np.random.default_rng(semente)
    medias = [diferenca[gerador.integers(0, len(diferenca), len(diferenca))].mean() for _ in range(sorteios)]
    minimo, maximo = np.percentile(medias, [2.5, 97.5])
    return round(diferenca.mean(), 4), round(minimo, 4), round(maximo, 4)

def tabela_calibracao(resultados, grupos=10):
    """Para cada resultado (H, D, A) e cada grupo de probabilidade prevista:
    número de jogos, probabilidade média prevista e frequência real."""
    linhas = []
    limites = np.linspace(0, 1, grupos + 1)
    for resultado in cfg.RESULTADOS_VALIDOS:
        previsto = resultados[f"Prob{resultado}"]
        aconteceu = (resultados["Resultado"] == resultado).astype(float)
        grupo = pd.cut(previsto, limites, include_lowest=True)
        tabela = (pd.DataFrame({"Grupo": grupo, "Previsto": previsto, "Real": aconteceu})
                  .groupby("Grupo", observed=True)
                  .agg(Jogos=("Real", "size"), Previsto=("Previsto", "mean"), Real=("Real", "mean"))
                  .reset_index())
        tabela.insert(0, "Resultado", resultado)
        linhas.append(tabela)
    return pd.concat(linhas, ignore_index=True)


def ece_por_resultado(resultados, grupos=10):
    """Erro de calibração de cada resultado (0 = perfeito) e a média dos três."""
    tabela = tabela_calibracao(resultados, grupos)
    tabela["Distancia"] = (tabela["Previsto"] - tabela["Real"]).abs() * tabela["Jogos"]
    ece = (tabela.groupby("Resultado")["Distancia"].sum() / len(resultados)).reindex(cfg.RESULTADOS_VALIDOS)
    ece["Média"] = ece.mean()
    return ece.round(4)