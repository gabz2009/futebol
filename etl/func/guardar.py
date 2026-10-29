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

from contextlib import closing

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
    with closing(sqlite3.connect(caminho_bd)) as ligacao:
        try:
            return pd.read_sql("SELECT * FROM etl_execucoes", ligacao)
        except pd.errors.DatabaseError:       # base criada antes de existir esta tabela
            return pd.DataFrame()


def registar_falha(caminho_bd, execucao):
    """Numa falha nada é recriado: só se acrescenta a linha ao histórico existente."""
    if not caminho_bd.exists():
        return
    with closing(sqlite3.connect(caminho_bd)) as ligacao:
        pd.DataFrame([execucao]).to_sql("etl_execucoes", ligacao, if_exists="append", index=False)
        ligacao.commit()


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

    try:
        os.replace(temporario, caminho_bd)   # troca instantânea: ou fica a base nova ou a antiga
    except PermissionError:
        # No Windows, um ficheiro aberto noutro programa não pode ser substituído
        logging.error(f"Não foi possível substituir {caminho_bd.name}: está aberto noutro programa "
                      "(separador do VS Code, notebook ou visualizador de SQLite). "
                      "Fecha-o e corre o ETL outra vez. A base de dados anterior ficou intacta.")
        raise SystemExit(1)
    logging.info(f"Base de dados atualizada: {caminho_bd}")

def substituir_tabelas(tabelas, caminho_bd, caminho_esquema):
    """Substitui só algumas tabelas numa base de dados que já existe
    (usado pela fase 2, que não recria a base toda).
    1. O esquema cria as tabelas "<tabela>_nova", com tipos e chaves.
    2. O Python enche essas tabelas.
    3. Numa única transação, as antigas são apagadas e as novas renomeadas.
    Se algo falhar antes do passo 3, as tabelas antigas ficam intactas."""
    with closing(sqlite3.connect(caminho_bd)) as ligacao:
        ligacao.execute("PRAGMA foreign_keys = ON")
        ligacao.executescript(caminho_esquema.read_text(encoding="utf-8"))
        for nome, tabela in tabelas.items():
            preparar_para_sqlite(tabela).to_sql(f"{nome}_nova", ligacao, if_exists="append", index=False)

        # Troca: tudo dentro da mesma transação (BEGIN ... COMMIT)
        ligacao.execute("BEGIN")
        for nome in tabelas:
            ligacao.execute(f'DROP TABLE IF EXISTS "{nome}"')
            ligacao.execute(f'ALTER TABLE "{nome}_nova" RENAME TO "{nome}"')
        ligacao.execute("COMMIT")

    for nome, tabela in tabelas.items():
        logging.info(f"Gravada a tabela {nome} ({len(tabela)} linhas)")