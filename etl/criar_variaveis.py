"""
=====================================================================
 FASE 2 - CRIAR AS VARIÁVEIS DO MODELO
=====================================================================
 COMO CORRER (depois do ETL)
   python etl/executar_etl.py
   python etl/criar_variaveis.py

 ATENÇÃO À ORDEM
   O ETL recria a base de dados de raiz, por isso apaga a tabela
   variaveis. Sempre que correres o ETL, corre este script a seguir.

 O QUE FAZ
   1. Lê as tabelas jogos e epocas do futebol.db.
   2. Calcula o Elo antes de cada jogo.
   3. Calcula as variáveis de forma de cada equipa (só jogos anteriores).
   4. Corre os controlos V01 a V05, incluindo o teste anti-fuga.
   5. Se não houver falhas críticas, grava na base de dados:
        - variaveis:     uma linha por jogo, pronta para o modelo
        - qa_variaveis:  resultado dos controlos
=====================================================================
"""
import logging
import sqlite3
import sys

import pandas as pd

from contextlib import closing

import configuracao as cfg
import func.controlos as controlos
import func.controlos_variaveis as controlos_variaveis
import func.elo as elo
import func.guardar as guardar
import func.pi_ratings as pi_ratings
import func.variaveis as variaveis_mod
import func.gap_ratings as gap_ratings


def configurar_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(cfg.PASTA_PROJETO / "dados" / "variaveis.log", mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    logging.captureWarnings(True)


def ler_tabelas():
    if not cfg.BASE_DADOS.exists():
        logging.error("Não existe futebol.db. Corre primeiro: python etl/executar_etl.py")
        sys.exit(1)
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        jogos = pd.read_sql("SELECT * FROM jogos", ligacao, parse_dates=["Data"])
        epocas = pd.read_sql("SELECT * FROM epocas", ligacao)
    return jogos, epocas


def main():
    configurar_log()
    controlos.iniciar()
    logging.info("Início da criação das variáveis")

    jogos, epocas = ler_tabelas()
    elo_jogos = elo.calcular_elo(jogos)
    pi_jogos = pi_ratings.calcular_pi_ratings(jogos)
    gap_jogos = gap_ratings.calcular_gap(jogos)
    variaveis = variaveis_mod.criar_variaveis(jogos, elo_jogos, pi_jogos, gap_jogos, epocas)

    logging.info(f"Variáveis calculadas: {len(variaveis)} jogos, "
                 f"{len(variaveis_mod.colunas_do_modelo(variaveis))} variáveis para o modelo")

    controlos_variaveis.controlo_uma_linha_por_jogo(variaveis, jogos)
    controlos_variaveis.controlo_sem_vazios(variaveis)
    controlos_variaveis.controlo_probabilidades(variaveis)
    controlos_variaveis.controlo_anti_fuga(jogos, epocas, variaveis, elo.calcular_elo, pi_ratings.calcular_pi_ratings, gap_ratings.calcular_gap)
    controlos_variaveis.controlo_elo(variaveis)
    controlos_variaveis.controlo_pi(variaveis)
    controlos_variaveis.controlo_gap(jogos, variaveis)

    if controlos.ha_falhas_criticas():
        logging.error("Falha crítica nos controlos das variáveis. Nada foi gravado.")
        sys.exit(1)

    guardar.substituir_tabelas({
        "variaveis": variaveis,
        "qa_variaveis": controlos.tabela_controlos(),
    }, cfg.BASE_DADOS, cfg.ESQUEMA_SQL_VARIAVEIS)
    logging.info("Variáveis gravadas em futebol.db")


if __name__ == "__main__":
    main()