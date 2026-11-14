"""
=====================================================================
 VERIFICAR UM CSV DESCARREGADO ANTES DE O GRAVAR
=====================================================================
 Um download pode correr mal sem dar erro: o site devolve uma página
 de erro em vez do CSV, ou o ficheiro chega cortado a meio. Antes de
 substituir o CSV que já funciona, confirma-se que o novo:
   1. tem as colunas mínimas (data, equipas, golos, resultado);
   2. não tem MENOS jogos do que o atual (uma época só cresce).
=====================================================================
"""
import io

import pandas as pd

import configuracao as cfg


def validar_csv(conteudo, jogos_atuais):
    """conteudo = bytes descarregados; jogos_atuais = jogos no CSV que já existe (0 se não existe).
    Devolve (tabela, None) se estiver bom, ou (None, motivo) se for de recusar."""
    try:
        tabela = pd.read_csv(io.BytesIO(conteudo), dtype=str, encoding="utf-8-sig")
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as erro:
        return None, f"não é um CSV válido ({erro.__class__.__name__})"
    em_falta = [c for c in cfg.COLUNAS_MINIMAS_CSV if c not in tabela.columns]
    if em_falta:
        return None, f"faltam colunas: {', '.join(em_falta)}"
    tabela = tabela.dropna(subset=["HomeTeam", "AwayTeam"])           # linhas vazias no fim do ficheiro
    if len(tabela) < jogos_atuais:
        return None, f"tem {len(tabela)} jogos e o atual tem {jogos_atuais} (download incompleto?)"
    return tabela, None