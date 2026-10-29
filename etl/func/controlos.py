"""
=====================================================================
 PASSO 3 - CONTROLOS DE QUALIDADE
=====================================================================
 O QUE FAZ
   Cada controlo compara um valor esperado com o valor obtido e
   regista o resultado numa lista. No fim, essa lista vai para a base
   de dados (tabela qa_controlos) e pode ser mostrada no Power BI.

 CRÍTICO OU INFORMATIVO?
   - Crítico: se falhar, os dados estão errados e o ETL PÁRA antes
     de gravar. A base de dados anterior fica intacta.
   - Informativo: só regista o que encontrou (ex.: odds em falta).
     Não é um erro, é uma característica dos dados que fica
     documentada.
=====================================================================
"""
import logging

import numpy as np
import pandas as pd

import configuracao as cfg

controlos = []

def iniciar():
    controlos.clear()

def registar(codigo, descricao, esperado, obtido, estado, critico, detalhe=""):
    controlos.append({
        "Controlo": codigo, "Descricao": descricao, "Esperado": str(esperado),
        "Obtido": str(obtido), "Estado": estado, "Critico": critico, "Detalhe": detalhe,
    })
    nivel = logging.error if (estado == "FALHA" and critico) else logging.info
    nivel(f"{codigo} {estado}: {descricao} (esperado {esperado}, obtido {obtido}) {detalhe}")


def controlo_ficheiros(tabelas):
    encontradas = sorted(tabelas)
    em_falta = [e for e in cfg.EPOCAS_ESPERADAS if e not in encontradas]
    a_mais = [e for e in encontradas if e not in cfg.EPOCAS_ESPERADAS]
    ok = not em_falta and not a_mais
    detalhe = f"em falta: {em_falta} | a mais: {a_mais}" if not ok else ""
    registar("C01", "Existe um ficheiro por cada época esperada",
             len(cfg.EPOCAS_ESPERADAS), len(encontradas), "OK" if ok else "FALHA", True, detalhe)


def controlo_colunas(colunas_em_falta):
    detalhe = "; ".join(f"{e}: {c}" for e, c in colunas_em_falta.items())
    registar("C02", "Todas as épocas têm as colunas obrigatórias",
             0, len(colunas_em_falta), "OK" if not colunas_em_falta else "FALHA", True, detalhe)


def controlo_jogos_por_epoca(jogos):
    contagem = jogos.groupby("Epoca")["JogoID"].count()
    completas = contagem.drop(cfg.EPOCA_ATUAL, errors="ignore")
    erradas = completas[completas != cfg.JOGOS_POR_EPOCA]
    detalhe = "; ".join(f"{e}: {n}" for e, n in erradas.items())
    registar("C03", f"Épocas completas têm {cfg.JOGOS_POR_EPOCA} jogos",
             0, len(erradas), "OK" if erradas.empty else "FALHA", True, detalhe)


def controlo_jogos_por_equipa(jogos):
    # Em cada época completa, cada equipa joga 34 vezes (17 em casa e 17 fora)
    completas = jogos[jogos["Epoca"] != cfg.EPOCA_ATUAL]
    casa = completas.groupby(["Epoca", "EquipaCasa"]).size()
    fora = completas.groupby(["Epoca", "EquipaFora"]).size()
    metade = cfg.JOGOS_POR_EQUIPA // 2
    erradas = pd.concat([casa[casa != metade], fora[fora != metade]])
    detalhe = "; ".join(f"{e} {eq}: {n}" for (e, eq), n in erradas.items())
    registar("C04", f"Cada equipa joga {metade} vezes em casa e {metade} fora (épocas completas)",
             0, len(erradas), "OK" if erradas.empty else "FALHA", True, detalhe)


def controlo_repetidos(jogos):
    repetidos = int(jogos["JogoID"].duplicated().sum())
    registar("C05", "Não há jogos repetidos (mesma época, casa e fora)",
             0, repetidos, "OK" if repetidos == 0 else "FALHA", True)


def controlo_valores_obrigatorios(jogos):
    # Depois da conversão, um valor vazio aqui significa que o original
    # estava vazio ou não era um número/data válida
    obrigatorias = ["Data", "EquipaCasa", "EquipaFora", "Resultado"] + cfg.COLUNAS_INTEIRAS
    vazios = jogos[obrigatorias].isna().sum()
    vazios = vazios[vazios > 0]
    detalhe = "; ".join(f"{c}: {n}" for c, n in vazios.items())
    registar("C06", "Datas, equipas, resultado e estatísticas sem valores vazios ou inválidos",
             0, int(vazios.sum()), "OK" if vazios.empty else "FALHA", True, detalhe)


def controlo_coerencia(jogos):
    # O resultado tem de bater com os golos
    calculado = np.select([jogos["GolosCasa"] > jogos["GolosFora"],
                           jogos["GolosCasa"] < jogos["GolosFora"]], ["H", "A"], default="D")
    regras = {
        "resultado diferente dos golos": calculado != jogos["Resultado"],
        "resultado inválido": ~jogos["Resultado"].isin(cfg.RESULTADOS_VALIDOS),
        "golos ao intervalo acima dos finais": (jogos["GolosCasaIntervalo"] > jogos["GolosCasa"])
                                               | (jogos["GolosForaIntervalo"] > jogos["GolosFora"]),
        "remates à baliza acima dos remates": (jogos["RematesBalizaCasa"] > jogos["RematesCasa"])
                                              | (jogos["RematesBalizaFora"] > jogos["RematesFora"]),
        "golos acima dos remates à baliza": (jogos["GolosCasa"] > jogos["RematesBalizaCasa"])
                                            | (jogos["GolosFora"] > jogos["RematesBalizaFora"]),
    }
    contagens = {nome: int(mascara.fillna(False).sum()) for nome, mascara in regras.items()}
    falhas = {nome: n for nome, n in contagens.items() if n > 0}
    # As 3 primeiras regras são impossíveis; a dos golos acima dos remates
    # pode acontecer com autogolos, por isso não é crítica
    criticas = {n: v for n, v in falhas.items() if n != "golos acima dos remates à baliza"}
    detalhe = "; ".join(f"{n}: {v}" for n, v in falhas.items())
    registar("C07", "Resultados e estatísticas coerentes entre si",
             0, sum(criticas.values()), "OK" if not criticas else "FALHA", True, detalhe)


def controlo_datas(jogos):
    # A época de cada jogo calculada pela data tem de ser igual à época do ficheiro.
    ano = jogos["Data"].dt.year.astype("Int64")
    ano_inicio = ano.where(jogos["Data"].dt.month >= cfg.MES_INICIO_EPOCA, ano - 1)
    epoca_pela_data = ano_inicio.astype(str).str[-2:] + "-" + (ano_inicio + 1).astype(str).str[-2:]
    erradas = jogos[epoca_pela_data != jogos["Epoca"]]
    detalhe = "; ".join(f"{f}: {n} jogos" for f, n in erradas.groupby("Ficheiro").size().items())
    registar("C08", "A época calculada pela data de cada jogo é a época do ficheiro",
             0, len(erradas), "OK" if erradas.empty else "FALHA", True, detalhe)


def controlo_odds(jogos):
    # Informativo: odds em falta não impedem a análise, ficam registadas
    vazios = jogos[cfg.COLUNAS_ODDS].isna().any(axis=1)
    jogos_sem_odds = jogos.loc[vazios, "JogoID"].tolist()
    registar("C09", "Jogos com alguma odd em falta", 0, len(jogos_sem_odds),
             "OK" if not jogos_sem_odds else "AVISO", False, "; ".join(jogos_sem_odds))
    return jogos.loc[vazios, ["JogoID", "Epoca", "Data", "EquipaCasa", "EquipaFora"] + cfg.COLUNAS_ODDS]

def controlo_odds_plausiveis(jogos):
    # Odds abaixo de 1 são impossíveis (perdia-se sempre dinheiro) e a
    # margem da casa (soma de 1/odd) tem de ficar num intervalo normal.
    # Jogos sem odds ficam de fora: já são tratados no C09.
    problemas = []
    for fonte in ["B365", "Media", "FechoB365", "FechoMedia"]:              # As odds de fecho só existem a partir de 2019-20                
        odds = jogos[[f"OddCasa{fonte}", f"OddEmpate{fonte}", f"OddFora{fonte}"]]
        abaixo_de_1 = (odds <= 1).any(axis=1)
        margem = (1 / odds).sum(axis=1, min_count=3)          # vazio se faltar alguma odd
        fora_do_intervalo = (margem < cfg.MARGEM_MIN) | (margem > cfg.MARGEM_MAX)
        for jogo in jogos.loc[abaixo_de_1 | fora_do_intervalo, "JogoID"]:
            problemas.append(f"{jogo} ({fonte})")
    registar("C11", f"Odds acima de 1 e margem entre {cfg.MARGEM_MIN} e {cfg.MARGEM_MAX}",
             0, len(problemas), "OK" if not problemas else "FALHA", True, "; ".join(problemas))


def controlo_hora(jogos):
    # Informativo: a hora não é usada nos cálculos, mas deve ter o formato HH:MM
    preenchidas = jogos["Hora"].dropna()
    invalidas = int((~preenchidas.str.fullmatch(r"\d{2}:\d{2}")).sum())
    registar("C12", "Horas preenchidas no formato HH:MM", 0, invalidas,
             "OK" if invalidas == 0 else "AVISO", False)


def controlo_nomes_equipas(equipas):
    # Informativo: quando sobe uma equipa nova, é preciso dar-lhe um nome
    # de apresentação em configuracao.py
    sem_nome = [e for e in equipas["Equipa"] if e not in cfg.NOMES_APRESENTACAO]
    registar("C13", "Todas as equipas têm nome de apresentação", 0, len(sem_nome),
             "OK" if not sem_nome else "AVISO", False, ", ".join(sem_nome))

def controlo_linhas(tabelas, jogos):
    lidas = sum(len(t) for t in tabelas.values())
    registar("C10", "Linhas lidas dos CSV = jogos na tabela final",
             lidas, len(jogos), "OK" if lidas == len(jogos) else "FALHA", True)


def tabela_controlos():
    return pd.DataFrame(controlos)


def ha_falhas_criticas():
    return any(c["Estado"] == "FALHA" and c["Critico"] for c in controlos)
