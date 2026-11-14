"""
=====================================================================
 CALENDÁRIO DA ÉPOCA ATUAL
=====================================================================
 O QUE FAZ
   Lê a resposta da API (dados/origem/calendario_<época>.json) e
   transforma-a numa tabela com um jogo por linha, os jogados e os
   que faltam, com os nomes das equipas iguais aos do resto do projeto.

 PORQUE É PRECISO
   O football-data.co.uk só tem os jogos já jogados. Para prever os
   jogos que faltam e simular o fim da época, é preciso saber quem
   joga com quem e quando.

 HORAS
   A API dá as horas em UTC. Passam para a hora de Lisboa, como as
   horas do football-data.co.uk.

 ESTADOS DE UM JOGO NA API
   SCHEDULED / TIMED: marcado (TIMED = já com hora certa)
   FINISHED: terminado     POSTPONED: adiado     IN_PLAY / PAUSED: a decorrer
=====================================================================
"""
import json

import pandas as pd
import numpy as np

import configuracao as cfg


def ler_calendario(caminho):
    """Devolve (tabela com um jogo por linha, data em que foi descarregado)."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    linhas = []
    for jogo in dados["matches"]:
        linhas.append({
            "IdAPI": jogo["id"],
            "Jornada": jogo["matchday"],
            "DataHoraUTC": jogo["utcDate"],
            "EquipaCasaAPI": jogo["homeTeam"]["name"],
            "EquipaForaAPI": jogo["awayTeam"]["name"],
            "Estado": jogo["status"],
            "GolosCasaAPI": jogo["score"]["fullTime"]["home"],
            "GolosForaAPI": jogo["score"]["fullTime"]["away"],
            "EmblemaCasaAPI": jogo["homeTeam"].get("crest"),
            "EmblemaForaAPI": jogo["awayTeam"].get("crest")
        })
    return pd.DataFrame(linhas), dados.get("descarregado_em")


def criar_calendario(origem):
    """Traduz os nomes, passa as horas para Lisboa e cria o JogoID igual ao da tabela jogos."""
    calendario = origem.copy()
    calendario["EquipaCasa"] = calendario["EquipaCasaAPI"].map(cfg.NOMES_API)
    calendario["EquipaFora"] = calendario["EquipaForaAPI"].map(cfg.NOMES_API)

    hora_lisboa = pd.to_datetime(calendario["DataHoraUTC"], utc=True).dt.tz_convert("Europe/Lisbon")
    calendario["Data"] = hora_lisboa.dt.strftime("%Y-%m-%d")
    calendario["Hora"] = hora_lisboa.dt.strftime("%H:%M")

    calendario.insert(0, "Epoca", cfg.EPOCA_ATUAL)
    calendario.insert(0, "JogoID", cfg.EPOCA_ATUAL + "_" + calendario["EquipaCasa"] + "_" + calendario["EquipaFora"])
    colunas = ["JogoID", "Epoca", "Jornada", "Data", "Hora", "EquipaCasa", "EquipaFora", "Estado", "IdAPI"]
    return calendario[colunas].sort_values(["Data", "Hora", "JogoID"]).reset_index(drop=True)


def jogos_por_jogar(calendario, jogos):
    """Os jogos do calendário que ainda não estão na tabela jogos, no formato da tabela jogos
    (golos, estatísticas, odds e resultado vazios), para se calcularem as suas variáveis.

    DATA PARA OS CÁLCULOS: um jogo por jogar é previsto com o que se sabe HOJE. Se a sua
    data já passou (um jogo adiado, ou terminado na API mas ainda sem dados no CSV), passa
    para o dia a seguir ao último jogo jogado. Senão, os ratings usados seriam os dessa
    data antiga, e não os mais recentes."""
    futuros = calendario[~calendario["JogoID"].isin(jogos["JogoID"])].copy()
    depois_do_ultimo = jogos["Data"].max() + pd.Timedelta(days=1)
    futuros["Data"] = pd.to_datetime(futuros["Data"]).clip(lower=depois_do_ultimo)
    futuros["EpocaCOVID"] = futuros["Epoca"].isin(cfg.EPOCAS_COVID)
    # As colunas que faltam (golos, estatísticas, odds, resultado) ficam vazias
    return futuros.reindex(columns=jogos.columns)

def jogos_terminados_api(calendario, origem, jogos):
    """Jogos que a API já dá como terminados mas que ainda não estão no CSV, no formato da
    tabela jogos: com golos e resultado, mas sem estatísticas nem odds (essas só chegam com o
    CSV, um ou dois dias depois). Assim o Elo, os pi-ratings, a forma e os modelos aprendem
    com o resultado logo que o jogo acaba. Quando o jogo chega ao CSV, sai daqui e entra a
    linha completa do CSV (o controlo C18 confirma que os golos batem certo)."""
    golos = calendario.merge(origem[["IdAPI", "GolosCasaAPI", "GolosForaAPI"]], on="IdAPI", validate="one_to_one")
    novos = golos[(golos["Estado"] == "FINISHED") & golos["GolosCasaAPI"].notna()
                  & ~golos["JogoID"].isin(jogos["JogoID"])].copy()
    novos["GolosCasa"] = novos["GolosCasaAPI"].astype(int)
    novos["GolosFora"] = novos["GolosForaAPI"].astype(int)
    diferenca = novos["GolosCasa"] - novos["GolosFora"]
    novos["Resultado"] = np.select([diferenca > 0, diferenca < 0], ["H", "A"], default="D")
    novos["TotalGolos"] = novos["GolosCasa"] + novos["GolosFora"]
    novos["Data"] = pd.to_datetime(novos["Data"])
    novos["Ficheiro"] = "API"           # para se saber de onde veio o resultado
    novos["EpocaCOVID"] = novos["Epoca"].isin(cfg.EPOCAS_COVID)
    # As colunas que faltam (estatísticas e odds) ficam vazias
    return novos.reindex(columns=jogos.columns)