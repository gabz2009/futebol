"""
=====================================================================
CARREGAR O DATA WAREHOUSE (PostgreSQL) PARA O POWER BI
=====================================================================
 COMO CORRER (depois do prever.py; o executar_tudo.py já o faz)
   python etl/carregar_warehouse.py

 ANTES DA PRIMEIRA VEZ
   1. PostgreSQL instalado, com a base "futebol", o schema "gold" e os
      utilizadores futebol_etl (escreve) e powerbi_leitor (só lê).
   2. No .env: PG_HOST, PG_PORTA, PG_BASE, PG_UTILIZADOR, PG_PALAVRA_PASSE.
   3. pip install sqlalchemy "psycopg[binary]"

 O QUE FAZ
   1. Lê as tabelas prontas do futebol.db e do historico.db.
   2. Transforma-as no esquema em estrela (func/warehouse.py).
   3. Apaga e volta a criar as tabelas do schema gold e carrega-as,
      tudo numa só transação.
   4. W01: confirma, antes de gravar de vez, que cada tabela do warehouse
      tem as linhas que saíram do Python. Se não tiver, desfaz tudo.
=====================================================================
"""
import json
import logging
import sqlite3
import sys
from contextlib import closing
from datetime import datetime

import pandas as pd

import configuracao as cfg
import func.controlos as controlos
import func.warehouse as warehouse


def configurar_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(cfg.PASTA_PROJETO / "dados" / "warehouse.log", mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    logging.captureWarnings(True)


def ler_fontes():
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        fontes = {nome: pd.read_sql(f"SELECT * FROM {nome}", ligacao)
                  for nome in ["equipas", "calendario", "previsoes", "avaliacao_oficial",
                               "simulacao_epoca", "simulacao_posicoes", "classificacao_jornada"]}
        # O último jogo da época atual que já está no CSV (com estatísticas e odds)
        fontes["ultimo_jogo_csv"] = ligacao.execute("SELECT MAX(Data) FROM jogos WHERE Epoca = ?",
                                                    (cfg.EPOCA_ATUAL,)).fetchone()[0]
        fontes["jogos_epoca"] = pd.read_sql("SELECT * FROM jogos WHERE Epoca = ?", ligacao, params=(cfg.EPOCA_ATUAL,))
        for tabela in ["espn_jogos", "jogadores_jogo", "estatisticas_equipa_espn"]:
            fontes[tabela] = pd.read_sql(f"SELECT * FROM {tabela}", ligacao)
        fontes["jogos_anteriores"] = pd.read_sql("SELECT Epoca, EquipaCasa, EquipaFora, GolosCasa, GolosFora "
                                                 "FROM jogos WHERE Epoca <> ?", ligacao, params=(cfg.EPOCA_ATUAL,))
    with closing(sqlite3.connect(cfg.BASE_HISTORICO)) as ligacao:
        fontes["historico"] = pd.read_sql("SELECT * FROM historico_simulacao", ligacao)
    # Quando o calendário foi descarregado da API (o descarregar_calendario.py grava-o no ficheiro)
    calendario_api = json.loads(cfg.FICHEIRO_CALENDARIO.read_text(encoding="utf-8"))
    fontes["calendario_descarregado_em"] = calendario_api.get("descarregado_em")
    fontes["carregado_em"] = datetime.now()
    fontes["previsoes_notebooks"], fontes["resumos_notebooks"] = ler_avaliacao_notebooks()
    return fontes


def ler_avaliacao_notebooks():
    """Os CSV da validação e do teste, juntos numa tabela só, com a fase em cada linha."""
    previsoes, resumos = [], []
    for fase, (ficheiro_previsoes, ficheiro_resumo) in cfg.FICHEIROS_AVALIACAO.items():
        previsoes.append(pd.read_csv(cfg.PASTA_AVALIACAO / ficheiro_previsoes).assign(Fase=fase))
        resumos.append(pd.read_csv(cfg.PASTA_AVALIACAO / ficheiro_resumo).assign(Fase=fase))
    return pd.concat(previsoes, ignore_index=True), pd.concat(resumos, ignore_index=True)


def verificar_env():
    if not cfg.FICHEIRO_CHAVE.exists():
        sys.exit(f"Não existe {cfg.FICHEIRO_CHAVE}.")
    env = warehouse.ler_env()
    em_falta = [nome for nome in cfg.VARIAVEIS_POSTGRES if not env.get(nome)]
    if em_falta:
        sys.exit(f"Faltam no .env: {', '.join(em_falta)}")
    return env


def main():
    configurar_log()
    controlos.iniciar()
    logging.info("Início do carregamento do data warehouse")

    env = verificar_env()
    tabelas = warehouse.tabelas_gold(ler_fontes())

    motor = warehouse.criar_motor(env)
    try:
        linhas = warehouse.carregar(tabelas, motor)
    except warehouse.CargaIncompleta as erro:
        controlos.registar("W01", "Linhas no warehouse iguais às preparadas no Python", 0, "-", "FALHA", True, str(erro))
        logging.error("Nada foi gravado no warehouse (a transação foi desfeita).")
        sys.exit(1)
    finally:
        motor.dispose()

    controlos.registar("W01", "Linhas no warehouse iguais às preparadas no Python", 0, 0, "OK", True,
                       "; ".join(f"{nome}: {n}" for nome, n in linhas.items()))
    logging.info(f"Warehouse carregado no schema {cfg.ESQUEMA_GOLD} ({len(tabelas)} tabelas)")


if __name__ == "__main__":
    main()