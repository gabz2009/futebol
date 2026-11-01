"""
=====================================================================
 HISTÓRICO DA SIMULAÇÃO, JORNADA A JORNADA
=====================================================================
 PARA QUE SERVE
   Guardar como estavam as probabilidades (título, top 3, Europa,
   descida) e os pontos esperados de cada equipa ANTES de cada jornada,
   para o Power BI mostrar a evolução e as variações (▲ / ▼).

 FOTOGRAFIA "DEPOIS DA JORNADA k"
   Corta-se a informação no início da jornada k+1 (a data do primeiro
   jogo dessa jornada): só entram os jogos do CSV antes dessa data.
   Com isso calculam-se as variáveis, as previsões e a simulação, como
   se fosse esse dia. A jornada 0 é o início da época.
   Como o projeto nunca usa informação do futuro, as fotografias das
   jornadas passadas podem ser reconstruídas a qualquer altura.

 QUANDO UMA FOTOGRAFIA ESTÁ PRONTA
   Quando todos os jogos marcados antes do corte já estão no CSV (os
   adiados não contam). Assim nunca se guarda uma fotografia a que
   faltam resultados.

 ONDE FICA
   Em dados/historico.db, uma base de dados à parte: a futebol.db é
   recriada em cada execução do ETL, a historico.db só cresce.
   Cada execução só calcula as fotografias que ainda não existem.
=====================================================================
"""
import sqlite3
from contextlib import closing

import pandas as pd

import configuracao as cfg
import func.calendario as calendario_mod
import func.elo as elo
import func.gap_ratings as gap_ratings
import func.pi_ratings as pi_ratings
import func.previsao as previsao
import func.simulacao as simulacao
import func.variaveis as variaveis_mod


def cortes_por_jornada(calendario):
    """Jornada (0 a 34) -> data do corte da fotografia: o primeiro jogo da jornada seguinte
    (ou, na última, o dia a seguir ao último jogo)."""
    marcados = calendario[calendario["Estado"] != "POSTPONED"]
    inicio = pd.to_datetime(marcados.groupby("Jornada")["Data"].min())
    cortes = pd.DataFrame({"Jornada": inicio.index - 1, "DataCorte": inicio.to_numpy()})
    # Fotografia final (depois da última jornada): no dia a seguir ao último jogo
    fim = pd.DataFrame({"Jornada": [int(calendario["Jornada"].max())],
                        "DataCorte": [pd.to_datetime(calendario["Data"]).max() + pd.Timedelta(days=1)]})
    return pd.concat([cortes, fim], ignore_index=True)


def fotografia_pronta(corte, calendario, jogos):
    """Todos os jogos marcados antes do corte já estão no CSV?"""
    antes = calendario[(pd.to_datetime(calendario["Data"]) < corte) & (calendario["Estado"] != "POSTPONED")]
    return antes["JogoID"].isin(jogos["JogoID"]).all()


def variaveis_ate(jogos, epocas, calendario):
    """As variáveis como estariam com estes jogos: jogos jogados + jogos da época ainda por jogar."""
    todos = pd.concat([jogos, calendario_mod.jogos_por_jogar(calendario, jogos)], ignore_index=True)
    return variaveis_mod.criar_variaveis(todos, elo.calcular_elo(todos), pi_ratings.calcular_pi_ratings(todos),
                                         gap_ratings.calcular_gap(todos), epocas)


def fotografia(jornada, corte, jogos, epocas, calendario, previsor_gb):
    """Simulação da época como estaria antes da jornada seguinte (só jogos antes do corte)."""
    jogos_corte = jogos[jogos["Data"] < corte]
    variaveis = variaveis_ate(jogos_corte, epocas, calendario)
    resultados, _ = previsao.prever_epoca(variaveis, jogos_corte, previsor_gb)
    tabela = previsao.tabela_previsoes(resultados, calendario, variaveis)
    conhecidos = jogos_corte.loc[jogos_corte["Epoca"] == cfg.EPOCA_ATUAL, ["JogoID", "GolosCasa", "GolosFora"]]
    jogos_epoca = simulacao.preparar_jogos(tabela, conhecidos)
    equipas, pontos, posicoes = simulacao.simular(jogos_epoca)
    resumo = simulacao.resumir(equipas, pontos, posicoes, simulacao.classificacao_atual(jogos_epoca))
    resumo.insert(0, "DataCorte", corte.strftime("%Y-%m-%d"))
    resumo.insert(0, "Jornada", int(jornada))
    resumo.insert(0, "Epoca", cfg.EPOCA_ATUAL)
    return resumo


def jornadas_guardadas(caminho):
    if not caminho.exists():
        return set()
    with closing(sqlite3.connect(caminho)) as ligacao:
        tabelas = {t for (t,) in ligacao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "historico_simulacao" not in tabelas:
            return set()
        linhas = ligacao.execute("SELECT DISTINCT Jornada FROM historico_simulacao WHERE Epoca = ?", (cfg.EPOCA_ATUAL,))
        return {j for (j,) in linhas}


def guardar(fotografias, caminho, caminho_esquema):
    """Acrescenta as fotografias novas. Se uma jornada já existir, é substituída (tudo numa transação)."""
    with closing(sqlite3.connect(caminho)) as ligacao:
        ligacao.executescript(caminho_esquema.read_text(encoding="utf-8"))     # CREATE TABLE IF NOT EXISTS
        with ligacao:       # transação: ou grava tudo, ou nada (se der erro, desfaz o DELETE)
            for (epoca, jornada) in fotografias[["Epoca", "Jornada"]].drop_duplicates().itertuples(index=False):
                ligacao.execute("DELETE FROM historico_simulacao WHERE Epoca = ? AND Jornada = ?", (epoca, int(jornada)))
            fotografias.to_sql("historico_simulacao", ligacao, if_exists="append", index=False)


def atualizar(calendario, jogos, epocas, previsor_gb, caminho=cfg.BASE_HISTORICO, caminho_esquema=cfg.ESQUEMA_HISTORICO_SQL):
    """Calcula e guarda as fotografias que ainda não existem e que já estão prontas.
    Devolve (número de jornadas no histórico, jornadas acrescentadas agora)."""
    guardadas = jornadas_guardadas(caminho)
    novas = []
    for jornada, corte in cortes_por_jornada(calendario).itertuples(index=False):
        if jornada in guardadas:
            continue
        if not fotografia_pronta(corte, calendario, jogos):
            break                   # as jornadas seguintes também não estão prontas
        novas.append(fotografia(jornada, corte, jogos, epocas, calendario, previsor_gb))
    if novas:
        guardar(pd.concat(novas, ignore_index=True), caminho, caminho_esquema)
    return len(guardadas) + len(novas), [int(f["Jornada"].iloc[0]) for f in novas]