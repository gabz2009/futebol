"""
=====================================================================
 PASSO 1 - LER OS FICHEIROS DE ORIGEM
=====================================================================
 O QUE FAZ
   Encontra os CSV na pasta de origem, lê cada um e junta duas
   colunas de rastreio:
     - Epoca: tirada do nome do ficheiro (P1_2017-18.csv -> 2017-18);
     - LinhaOrigem: o número da linha no CSV, para se conseguir
       voltar sempre ao ficheiro original.
   Nesta fase NÃO se muda nada nos dados: cada ficheiro é guardado
   tal como veio, com as suas próprias colunas.
=====================================================================
"""
import logging
import re

import pandas as pd

import configuracao as cfg


def epoca_do_ficheiro(caminho):
    """P1_2017-18.csv -> '2017-18'. Devolve None se o nome não seguir o padrão."""
    encontrado = re.search(r"(\d{2}-\d{2})", caminho.stem)
    return encontrado.group(1) if encontrado else None


def listar_ficheiros():
    ficheiros = sorted(cfg.PASTA_ORIGEM.glob(cfg.PADRAO_FICHEIROS))
    logging.info(f"Encontrados {len(ficheiros)} ficheiros em {cfg.PASTA_ORIGEM}")
    return ficheiros


def ler_ficheiro(caminho):
    # dtype=str: lemos tudo como texto e só convertemos no passo seguinte,
    # onde cada conversão é controlada. Assim nada é "adivinhado" pelo pandas.
    # utf-8-sig: aceita ficheiros com ou sem BOM no início.
    tabela = pd.read_csv(caminho, dtype=str, encoding="utf-8-sig")

    # Algumas exportações trazem colunas vazias no fim (Unnamed: 64...)
    tabela = tabela.loc[:, ~tabela.columns.str.startswith("Unnamed")]
    # E linhas completamente vazias no fim do ficheiro
    tabela = tabela.dropna(how="all")

    tabela.insert(0, "Epoca", epoca_do_ficheiro(caminho))
    tabela.insert(1, "Ficheiro", caminho.name)
    # +2: a linha 1 do CSV é o cabeçalho, o primeiro jogo está na linha 2
    tabela.insert(2, "LinhaOrigem", range(2, len(tabela) + 2))

    logging.info(f"{caminho.name}: {len(tabela)} jogos, {tabela.shape[1] - 3} colunas de origem")
    return tabela


def ler_todos():
    """Devolve um dicionário {época: tabela}, uma tabela por ficheiro."""
    tabelas = {}
    for caminho in listar_ficheiros():
        epoca = epoca_do_ficheiro(caminho)
        if epoca is None:
            logging.warning(f"{caminho.name} ignorado: o nome não tem a época (ex.: P1_2017-18.csv)")
            continue
        tabelas[epoca] = ler_ficheiro(caminho)
    return tabelas

def juntar_origem(tabelas):
    return pd.concat(tabelas.values(), ignore_index=True)