"""
=====================================================================
 PASSO 2 - UNIFORMIZAR AS ÉPOCAS NUMA SÓ TABELA
=====================================================================
 O QUE FAZ
   1. Em cada época, troca os nomes antigos das colunas pelos novos
      (BbAvH -> AvgH...) e verifica se estão todas as colunas precisas.
   2. Fica só com as colunas definidas na configuração e dá-lhes nomes
      em português.
   3. Junta as 10 épocas numa só tabela (jogos).
   4. Converte os tipos: datas, inteiros e decimais.
   5. Cria uma chave única por jogo e as tabelas de equipas e épocas.

 PORQUE SE VERIFICAM AS COLUNAS ANTES DE JUNTAR?
   Se uma época não tiver uma coluna obrigatória, queremos saber
   QUAL época e QUAL coluna, em vez de descobrir mais tarde um
   buraco de valores vazios sem explicação.
=====================================================================
"""
import logging

import pandas as pd

import configuracao as cfg


def uniformizar_epoca(tabela):
    """Devolve (tabela uniformizada, lista de colunas obrigatórias em falta)."""
    tabela = tabela.rename(columns=cfg.MAPA_NOMES_ANTIGOS)

    em_falta = []
    for coluna in cfg.COLUNAS_FINAIS:
        if coluna not in tabela.columns:
            if coluna in cfg.COLUNAS_OPCIONAIS:
                tabela[coluna] = pd.NA            # ex.: Hora antes de 2019-20
            else:
                em_falta.append(coluna)

    if em_falta:
        return None, em_falta

    tabela = tabela[cfg.COLUNAS_RASTREIO + list(cfg.COLUNAS_FINAIS)]
    tabela = tabela.rename(columns=cfg.COLUNAS_FINAIS)
    return tabela, []


def juntar_epocas(tabelas):
    """Devolve (jogos, colunas_em_falta) com colunas_em_falta = {época: [colunas]}."""
    uniformizadas = []
    colunas_em_falta = {}
    for epoca, tabela in tabelas.items():
        uniformizada, em_falta = uniformizar_epoca(tabela)
        if em_falta:
            colunas_em_falta[epoca] = em_falta
            logging.warning(f"{epoca}: faltam as colunas {em_falta}")
        else:
            uniformizadas.append(uniformizada)

    jogos = pd.concat(uniformizadas, ignore_index=True)
    return jogos, colunas_em_falta


def converter_tipos(jogos):
    jogos = jogos.copy()

    # Texto: tirar espaços a mais nos nomes e nos resultados
    for coluna in ["EquipaCasa", "EquipaFora", "Resultado", "ResultadoIntervalo"]:
        jogos[coluna] = jogos[coluna].str.strip()

    # Datas: 2017-18 usa dd/mm/aa e as restantes dd/mm/aaaa.
    # Tentamos os dois formatos de forma explícita, em vez de deixar
    # o pandas adivinhar (podia trocar o dia com o mês).
    data_curta = pd.to_datetime(jogos["Data"], format="%d/%m/%y", errors="coerce")
    data_longa = pd.to_datetime(jogos["Data"], format="%d/%m/%Y", errors="coerce")
    jogos["Data"] = data_longa.fillna(data_curta)

    # errors="coerce": um valor que não seja número fica vazio e é
    # apanhado nos controlos, em vez de parar o programa aqui
    for coluna in cfg.COLUNAS_INTEIRAS:
        jogos[coluna] = pd.to_numeric(jogos[coluna], errors="coerce").astype("Int64")
    for coluna in cfg.COLUNAS_ODDS + cfg.COLUNAS_ODDS_FECHO:
        jogos[coluna] = pd.to_numeric(jogos[coluna], errors="coerce")

    jogos["LinhaOrigem"] = jogos["LinhaOrigem"].astype(int)
    return jogos


def acrescentar_colunas(jogos):
    jogos = jogos.copy()
    # Chave única: numa época, cada equipa recebe cada adversário uma só vez
    jogos.insert(0, "JogoID", jogos["Epoca"] + "_" + jogos["EquipaCasa"] + "_" + jogos["EquipaFora"])
    jogos["TotalGolos"] = jogos["GolosCasa"] + jogos["GolosFora"]
    jogos["EpocaCOVID"] = jogos["Epoca"].isin(cfg.EPOCAS_COVID)
    return jogos.sort_values(["Data", "Hora", "EquipaCasa"], na_position="first").reset_index(drop=True)


def criar_equipas(jogos):
    # Uma linha por equipa e época em que jogou (casa e fora juntas)
    presencas = pd.concat([
        jogos[["Epoca", "EquipaCasa"]].rename(columns={"EquipaCasa": "Equipa"}),
        jogos[["Epoca", "EquipaFora"]].rename(columns={"EquipaFora": "Equipa"}),
    ]).drop_duplicates()

    equipas = (presencas.groupby("Equipa")["Epoca"]
               .agg(PrimeiraEpoca="min", UltimaEpoca="max", NumEpocas="nunique")
               .reset_index())
    equipas.insert(1, "NomeApresentacao", equipas["Equipa"].map(cfg.NOMES_APRESENTACAO).fillna(equipas["Equipa"]))
    equipas["Nota"] = equipas["Equipa"].map(cfg.NOTAS_EQUIPAS)
    return equipas


def criar_epocas(jogos):
    epocas = (jogos.groupby("Epoca")
              .agg(Inicio=("Data", "min"), Fim=("Data", "max"), Jogos=("JogoID", "count"))
              .reset_index())
    epocas["Completa"] = epocas["Jogos"] == cfg.JOGOS_POR_EPOCA
    epocas["Uso"] = epocas["Epoca"].map(cfg.USO_EPOCA)
    epocas["COVID"] = epocas["Epoca"].isin(cfg.EPOCAS_COVID)
    return epocas
