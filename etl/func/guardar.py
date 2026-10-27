"""
=====================================================================
 PASSO 4 - GRAVAR NA BASE DE DADOS SQLITE
=====================================================================
 PORQUE SQLITE E NÃO CSV?
   - Uma base de dados é um só ficheiro (futebol.db) com várias
     tabelas, em vez de muitos CSV soltos.
   - Os tipos e as chaves ficam definidos (ver esquema.sql).
   - O sqlite3 já vem com o Python: não há nada para instalar.

 GRAVAÇÃO "TUDO OU NADA"
   Tudo é gravado primeiro num ficheiro temporário (futebol.db.tmp).
   Só no fim, se tudo correu bem, esse ficheiro substitui o
   futebol.db com os.replace, que é uma troca instantânea.
   Se houver um erro a meio, o futebol.db antigo fica intacto.

 HISTÓRICO DE EXECUÇÕES
   Como a base de dados é recriada em cada execução, a tabela
   etl_execucoes é lida da base antiga antes de ser substituída,
   para não se perder o histórico.
=====================================================================
"""
import logging
import os
import sqlite3

import pandas as pd


def preparar_para_sqlite(tabela):
    tabela = tabela.copy()
    # Datas em texto ISO (2017-08-06): é o formato que o SQLite entende
    for coluna in tabela.columns:
        if str(tabela[coluna].dtype).startswith("datetime"):
            tabela[coluna] = tabela[coluna].dt.strftime("%Y-%m-%d")
    return tabela


def ler_execucoes_anteriores(caminho_bd):
    """Devolve o histórico de execuções da base atual (vazio se não existir)."""
    if not caminho_bd.exists():
        return pd.DataFrame()
    with sqlite3.connect(caminho_bd) as ligacao:
        try:
            return pd.read_sql("SELECT * FROM etl_execucoes", ligacao)
        except pd.errors.DatabaseError:       # base criada antes de existir esta tabela
            return pd.DataFrame()


def registar_falha(caminho_bd, execucao):
    """Numa falha nada é recriado: só se acrescenta a linha ao histórico existente."""
    if not caminho_bd.exists():
        return
    with sqlite3.connect(caminho_bd) as ligacao:
        pd.DataFrame([execucao]).to_sql("etl_execucoes", ligacao, if_exists="append", index=False)


def gravar_tabelas(tabelas, caminho_bd, caminho_esquema):
    """tabelas = dicionário {nome da tabela: DataFrame}, pela ordem de gravação.
    As tabelas referidas por chaves estrangeiras têm de vir primeiro
    (equipas e epocas antes de jogos)."""
    caminho_bd.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho_bd.with_name(caminho_bd.name + ".tmp")
    temporario.unlink(missing_ok=True)        # restos de uma execução que falhou

    ligacao = sqlite3.connect(temporario)
    try:
        ligacao.execute("PRAGMA foreign_keys = ON")     # o SQLite só verifica as chaves estrangeiras com isto
        ligacao.executescript(caminho_esquema.read_text(encoding="utf-8"))
        for nome, tabela in tabelas.items():
            # "append": a tabela já foi criada pelo esquema, só se inserem as linhas
            preparar_para_sqlite(tabela).to_sql(nome, ligacao, if_exists="append", index=False)
            logging.info(f"Gravada a tabela {nome} ({len(tabela)} linhas)")
        ligacao.commit()
    finally:
        ligacao.close()

    os.replace(temporario, caminho_bd)       # troca instantânea: ou fica a base nova ou a antiga
    logging.info(f"Base de dados atualizada: {caminho_bd}")