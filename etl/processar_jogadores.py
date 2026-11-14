"""
=====================================================================
 TRATAR AS FICHAS DOS JOGOS (ESPN)
=====================================================================
 COMO CORRER (o executar_tudo.py já o corre, a seguir ao executar_etl.py)
   python etl/processar_jogadores.py

 O QUE FAZ
   Lê as fichas gravadas em dados/origem/espn/ pelo
   descarregar_jogadores.py, transforma-as em tabelas e grava-as na
   futebol.db (que o executar_etl.py acabou de criar):
     - espn_equipas:             nome da ESPN -> nome do nosso CSV
     - espn_jogos:               um jogo por linha, com o nosso JogoID
     - jogadores_jogo:           um jogador da ficha por jogo (minutos,
                                 estatísticas, golos com ele em campo)
     - eventos_jogo:             golos, substituições e cartões
     - estatisticas_equipa_espn: posse e passes de cada equipa por jogo

 CONTROLOS
   - Cada ficha tem de ficar ligada a um JogoID nosso (crítico: se
     falhar, pára sem gravar).
   - Os golos dos eventos têm de dar o resultado final (aviso).
   - Posições da ESPN que não sabemos em que linha pôr (aviso).
=====================================================================
"""
import json
import logging
import sqlite3
import sys
from contextlib import closing

import pandas as pd

import configuracao as cfg
import func.espn as espn

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def ler_fichas():
    jogos, eventos, jogadores, equipas = [], [], [], []
    for caminho in sorted(cfg.PASTA_ESPN.glob("*.json")):
        ficha = json.loads(caminho.read_text(encoding="utf-8"))
        evento_id = caminho.stem.split("_")[1]
        jogo = espn.jogo_da_ficha(ficha, evento_id)
        eventos_jogo = espn.eventos_da_ficha(ficha, evento_id)
        jogos.append(jogo)
        eventos.append(eventos_jogo)
        jogadores.append(espn.jogadores_da_ficha(ficha, evento_id, eventos_jogo, jogo["Duracao"]))
        equipas.append(espn.estatisticas_equipa_da_ficha(ficha, evento_id))
    return (pd.DataFrame(jogos), pd.concat(eventos, ignore_index=True),
            pd.concat(jogadores, ignore_index=True), pd.concat(equipas, ignore_index=True))


def main():
    log.info("Início do tratamento das fichas da ESPN")
    if not any(cfg.PASTA_ESPN.glob("*.json")):
        sys.exit(f"Não há fichas em {cfg.PASTA_ESPN}: corre primeiro o descarregar_jogadores.py")
    jogos, eventos, jogadores, equipas = ler_fichas()

    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        calendario = pd.read_sql("SELECT c.JogoID, c.Data, c.EquipaCasa, c.EquipaFora, "
                                 "o.GolosCasaAPI AS GolosCasa, o.GolosForaAPI AS GolosFora "
                                 "FROM calendario c JOIN origem_calendario o ON o.IdAPI = c.IdAPI", ligacao)
    calendario[["GolosCasa", "GolosFora"]] = calendario[["GolosCasa", "GolosFora"]].astype("Int64")

    # Nomes da ESPN -> nomes do CSV, e cada jogo ao nosso JogoID (numa época, cada par casa/fora só joga uma vez)
    mapa = espn.mapear_equipas(jogos, calendario)
    nome = dict(zip(mapa["EquipaESPN"], mapa["Equipa"]))
    jogos["EquipaCasa"] = jogos["EquipaCasaESPN"].map(nome)
    jogos["EquipaFora"] = jogos["EquipaForaESPN"].map(nome)
    jogos = jogos.merge(calendario[["JogoID", "EquipaCasa", "EquipaFora"]], on=["EquipaCasa", "EquipaFora"], how="left")
    jogo_id = dict(zip(jogos["EventoID"], jogos["JogoID"]))
    for tabela in (eventos, jogadores, equipas):
        tabela.insert(0, "JogoID", tabela["EventoID"].map(jogo_id))
        tabela.insert(2, "Equipa", tabela["EquipaESPN"].map(nome))

    sem_jogo = jogos[jogos["JogoID"].isna()]
    if len(sem_jogo):
        sys.exit(f"CRÍTICO: {len(sem_jogo)} fichas sem JogoID (equipas por ligar?):\n"
                 f"{sem_jogo[['EventoID', 'NomeCasaESPN', 'NomeForaESPN']].to_string(index=False)}\nNada foi gravado.")
    golos_errados = espn.golos_que_nao_batem(jogos, eventos)
    if len(golos_errados):
        log.warning("Jogos em que os golos dos eventos não dão o resultado:\n%s", golos_errados.to_string(index=False))
    sem_lugar = jogadores[(jogadores["Titular"] == 1) & jogadores["CampoX"].isna()]
    if len(sem_lugar):
        log.warning("Titulares sem lugar no campo (formação e posição em falta no CAMPO_POR_FORMACAO): %s",
                    sem_lugar.groupby(["Formacao", "PosicaoCurta"]).size().to_dict())
    sem_linha = jogadores.loc[jogadores["Linha"].isna() & (jogadores["Minutos"] > 0) & (jogadores["Posicao"] != "Substitute"), "Posicao"].value_counts()
    if len(sem_linha):
        log.warning("Posições da ESPN sem linha (jogadores que jogaram): %s", sem_linha.to_dict())

    tabelas = {"espn_equipas": mapa, "espn_jogos": jogos, "jogadores_jogo": jogadores,
               "eventos_jogo": eventos, "estatisticas_equipa_espn": equipas}
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao, ligacao:
        for nome_tabela, tabela in tabelas.items():
            tabela.to_sql(nome_tabela, ligacao, if_exists="replace", index=False)
    log.info("Gravado na futebol.db: %s", "; ".join(f"{n}: {len(t)}" for n, t in tabelas.items()))


if __name__ == "__main__":
    main()