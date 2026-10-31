"""
=====================================================================
 FASE 7 - PREVISÕES DA ÉPOCA ATUAL
=====================================================================
 COMO CORRER (depois do ETL e das variáveis; o executar_tudo.py já o faz)
   python etl/prever.py

 O QUE FAZ
   1. Lê as variáveis (jogos jogados e por jogar), os jogos e o calendário.
   2. Prevê os 306 jogos da época atual com o modelo final (média
      geométrica da Ordinal, do Dixon-Coles e do boosting), treinado com
      todas as épocas anteriores e, no modo semanal, com os jogos da
      própria época já jogados antes de cada semana.
   3. Avalia os jogos já jogados da época atual contra as odds: é um
      teste novo, porque nenhum modelo os viu.
   4. Corre os controlos P01 a P03 e grava as tabelas previsoes e
      qa_previsoes (para o Power BI).
=====================================================================
"""
import logging
import sqlite3
import sys
from contextlib import closing

import numpy as np
import pandas as pd

import configuracao as cfg
import func.avaliacao as av
import func.boosting as gb
import func.controlos as controlos
import func.dixon_coles as dc
import func.guardar as guardar
import func.ordinal as ordinal
import func.previsao as previsao
from func.variaveis import colunas_do_modelo

USO = "Previsão"


def configurar_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(cfg.PASTA_PROJETO / "dados" / "previsoes.log", mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    logging.captureWarnings(True)


def ler_tabelas():
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        variaveis = pd.read_sql("SELECT * FROM variaveis ORDER BY Data, JogoID", ligacao)
        jogos = pd.read_sql("SELECT JogoID, Epoca, Data, EquipaCasa, EquipaFora, GolosCasa, GolosFora FROM jogos", ligacao)
        calendario = pd.read_sql("SELECT * FROM calendario", ligacao)
    return variaveis, jogos, calendario


def prever_epoca(variaveis, jogos):
    resultados = {
        "Ordinal": av.walk_forward(variaveis, previsao.semana_a_semana(ordinal.criar_previsor(cfg.COLUNAS_ORDINAL)), USO),
        "DixonColes": av.walk_forward(variaveis, dc.criar_previsor(jogos), USO),      # já se ajusta todas as semanas
    }
    previsor_gb = gb.criar_previsor(colunas_do_modelo(variaveis))
    resultados["Boosting"] = av.walk_forward(variaveis, previsao.semana_a_semana(previsor_gb), USO)
    logging.info(f"Boosting, parâmetros escolhidos no início da época: {previsor_gb.escolhidos}")
    resultados["Modelo final"] = av.media_geometrica([resultados[m] for m in ["Ordinal", "DixonColes", "Boosting"]])
    return resultados


def avaliar_jogados(resultados, variaveis):
    """Os jogos já jogados da época atual: modelo final contra as odds (informativo)."""
    def odds(tipo):
        colunas = [f"ProbOdds{tipo}Casa", f"ProbOdds{tipo}Empate", f"ProbOdds{tipo}Fora"]
        return lambda treino, teste: teste[colunas].to_numpy()

    tabelas = {"Modelo final": resultados["Modelo final"],
               "Odds pré-jogo": av.walk_forward(variaveis, odds(""), USO),
               "Odds de fecho": av.walk_forward(variaveis, odds("Fecho"), USO)}
    jogados = {nome: t[t["Resultado"].notna()].reset_index(drop=True) for nome, t in tabelas.items()}
    resumo = av.resumo(jogados)
    linhas = "; ".join(f"{r.Modelo}: log loss {r.LogLoss:.4f}, acerto {r.Acerto:.1%}" for r in resumo.itertuples())
    diferenca, minimo, maximo = av.comparar(jogados["Modelo final"], jogados["Odds pré-jogo"])
    controlos.registar("P03", "Jogos jogados da época atual: modelo final contra as odds (informativo)",
                       "-", len(jogados["Modelo final"]), "OK", False,
                       f"{linhas} | modelo final - odds pré-jogo: {diferenca:+.4f} [{minimo:+.4f}, {maximo:+.4f}]")


def controlar(tabela, calendario):
    # P01: um jogo por linha, os mesmos jogos do calendário
    certos = len(tabela) == len(calendario) and set(tabela["JogoID"]) == set(calendario["JogoID"])
    controlos.registar("P01", "Uma previsão por cada jogo do calendário", len(calendario), len(tabela),
                       "OK" if certos else "FALHA", True)
    # P02: probabilidades entre 0 e 1 e a somar 1, no modelo final e em cada modelo
    colunas = [c for c in tabela.columns if c.startswith("Prob") and "Odds" not in c]
    valores = tabela[colunas].to_numpy()
    somas = [tabela[[f"ProbCasa{m}", f"ProbEmpate{m}", f"ProbFora{m}"]].sum(axis=1)
             for m in ["", "Ordinal", "DixonColes", "Boosting"]]
    erradas = int(((valores <= 0) | (valores >= 1)).any(axis=1).sum()
                  + sum(((s - 1).abs() > 1e-9).sum() for s in somas))
    controlos.registar("P02", "Probabilidades entre 0 e 1 e a somar 1 (modelo final e cada modelo)", 0, erradas,
                       "OK" if erradas == 0 else "FALHA", True)


def main():
    configurar_log()
    controlos.iniciar()
    logging.info("Início das previsões da época atual")

    variaveis, jogos, calendario = ler_tabelas()
    resultados = prever_epoca(variaveis, jogos)
    tabela = previsao.tabela_previsoes(resultados, calendario, variaveis)
    logging.info(f"Previsões: {len(tabela)} jogos ({int(tabela['Jogado'].sum())} jogados, "
                 f"{int((tabela['Jogado'] == 0).sum())} por jogar)")

    controlar(tabela, calendario)
    avaliar_jogados(resultados, variaveis)
    if controlos.ha_falhas_criticas():
        logging.error("Falha crítica nos controlos das previsões. Nada foi gravado.")
        sys.exit(1)

    guardar.substituir_tabelas({"previsoes": tabela, "qa_previsoes": controlos.tabela_controlos()},
                               cfg.BASE_DADOS, cfg.ESQUEMA_PREVISOES_SQL)
    logging.info("Previsões gravadas em futebol.db")


if __name__ == "__main__":
    main()