"""
=====================================================================
 EMBLEMAS DOS CLUBES
=====================================================================
 DE ONDE VÊM (por ordem de prioridade)
   1. Manual (cfg.EMBLEMAS_MANUAIS): para corrigir à mão uma equipa.
   2. TheSportsDB: a fonte principal, para as 30 equipas terem todos o
      mesmo estilo de imagem.
   3. football-data.org (a API do calendário): só tem as equipas da
      época atual; serve de reserva se o TheSportsDB falhar.

 ESCOLHER A EQUIPA CERTA NA PESQUISA
   Pesquisar "Porto" devolve o FC Porto, o FC Porto B, equipas de
   outros países... Fica-se só com futebol masculino de Portugal e,
   se ainda houver mais do que uma, com a que está na Primeira Liga
   ou cujo nome é igual ao pesquisado. Se não der para decidir, a
   equipa fica sem emblema do TheSportsDB e o controlo C20 avisa.
=====================================================================
"""
import json
import unicodedata

import pandas as pd

import configuracao as cfg


def normalizar(texto):
    """Minúsculas e sem acentos: 'Famalicão' -> 'famalicao'."""
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acentos.lower().strip()


def escolher_equipa(candidatas, termo):
    """Devolve a equipa certa entre os resultados da pesquisa, ou None se não der para decidir."""
    portuguesas = [c for c in (candidatas or [])
                   if c.get("strSport") == "Soccer" and c.get("strCountry") == "Portugal"
                   and c.get("strGender", "Male") != "Female"]
    for criterio in (lambda c: True,
                     lambda c: c.get("strLeague") == "Portuguese Primeira Liga",
                     lambda c: normalizar(c.get("strTeam", "")) == normalizar(termo)):
        escolhidas = [c for c in portuguesas if criterio(c)]
        if len(escolhidas) == 1:
            return escolhidas[0]
    return None


def emblemas_thesportsdb(caminho):
    """Equipa -> endereço do emblema, a partir das respostas guardadas. Também devolve as que falharam."""
    if not caminho.exists():
        return {}, sorted(cfg.NOMES_APRESENTACAO)
    respostas = json.loads(caminho.read_text(encoding="utf-8"))["respostas"]
    emblemas, falharam = {}, []
    for equipa, resposta in respostas.items():
        escolhida = escolher_equipa(resposta["equipas"], resposta["pesquisa"])
        badge = escolhida and (escolhida.get("strBadge") or escolhida.get("strTeamBadge"))
        if badge:
            emblemas[equipa] = badge
        else:
            falharam.append(equipa)
    return emblemas, falharam


def emblemas_football_data(origem_calendario):
    """Equipa (nome da API) -> emblema, com os nomes traduzidos para os nossos."""
    casa = origem_calendario[["EquipaCasaAPI", "EmblemaCasaAPI"]].set_axis(["Nome", "Emblema"], axis=1)
    fora = origem_calendario[["EquipaForaAPI", "EmblemaForaAPI"]].set_axis(["Nome", "Emblema"], axis=1)
    todos = pd.concat([casa, fora]).dropna().drop_duplicates("Nome")
    return {cfg.NOMES_API[n]: e for n, e in zip(todos["Nome"], todos["Emblema"]) if n in cfg.NOMES_API}


def juntar_emblemas(equipas, emblemas_tsdb, emblemas_fd):
    """Acrescenta EmblemaURL e EmblemaFonte à tabela equipas, pela ordem de prioridade."""
    equipas = equipas.copy()
    fontes = [("Manual", cfg.EMBLEMAS_MANUAIS), ("TheSportsDB", emblemas_tsdb), ("football-data.org", emblemas_fd)]
    equipas["EmblemaURL"], equipas["EmblemaFonte"] = None, None
    for nome_fonte, emblemas in reversed(fontes):        # a última a escrever é a de maior prioridade
        tem = equipas["Equipa"].isin(emblemas)
        equipas.loc[tem, "EmblemaURL"] = equipas.loc[tem, "Equipa"].map(emblemas)
        equipas.loc[tem, "EmblemaFonte"] = nome_fonte
    return equipas