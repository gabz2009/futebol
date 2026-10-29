"""
=====================================================================
 TESTE DA GRAVAÇÃO "TUDO OU NADA"
=====================================================================
 Se a gravação falhar a meio, a base de dados anterior tem de ficar
 exatamente como estava. tmp_path é uma pasta temporária que o
 pytest cria para o teste e apaga no fim.
=====================================================================
"""
import sqlite3
from contextlib import closing

import pandas as pd
import pytest

import func.guardar as guardar


def test_falha_a_meio_deixa_a_base_anterior_intacta(tmp_path):
    esquema = tmp_path / "esquema.sql"
    esquema.write_text("CREATE TABLE t (x INTEGER NOT NULL);", encoding="utf-8")
    base = tmp_path / "teste.db"

    # 1.ª gravação, correta: 3 linhas
    guardar.gravar_tabelas({"t": pd.DataFrame({"x": [1, 2, 3]})}, base, esquema)

    # 2.ª gravação, com um valor vazio numa coluna NOT NULL: tem de falhar
    with pytest.raises(Exception):
        guardar.gravar_tabelas({"t": pd.DataFrame({"x": [10, None]})}, base, esquema)

    # A base continua com as 3 linhas da 1.ª gravação
    with closing(sqlite3.connect(base)) as ligacao:
        assert pd.read_sql("SELECT x FROM t", ligacao)["x"].tolist() == [1, 2, 3]