"""
=====================================================================
 PI-RATINGS (Constantinou e Fenton, 2013)
=====================================================================
 O QUE SÃO
   Cada equipa tem DOIS ratings: um quando joga em casa e outro
   quando joga fora. Começam em 0 (equipa média). O rating mede
   quantos golos a equipa marca a mais do que uma equipa média,
   numa escala comprimida: rating 1,0 = cerca de +1,15 golos.

 AS CONTAS DE UM JOGO
   1. Golos esperados de cada equipa contra uma equipa média:
        g = 10 ^ (|rating| / 3) - 1, com o sinal do rating
      (casa: rating em casa; fora: rating fora)
   2. Diferença esperada = g_casa - g_fora
   3. Erro = |diferença real - diferença esperada|
   4. Erro comprimido = 3 x log10(1 + erro)
      (erros enormes não estragam os ratings)
   5. Atualização:
      - rating em casa da casa e rating fora da de fora mudam
        erro comprimido x LAMBDA
      - os outros dois ratings mudam GAMMA (70%) disso
      Quem jogou acima do esperado sobe, quem jogou abaixo desce.

 FONTE DAS FÓRMULAS E DOS PARÂMETROS
   Implementação de referência do pacote R "piratings"
   (calculate_pi_ratings), feita a partir do artigo original.
   Valores por defeito: lambda = 0.035, gamma = 0.7, b = 10, c = 3.

 SEM FUGA DE INFORMAÇÃO
   Como no Elo, guarda-se o rating de ANTES do jogo. O resultado só
   atualiza os ratings para os jogos seguintes.

 EQUIPAS PROMOVIDAS (decisão nossa, não do artigo)
   No artigo uma equipa nova começa em 0 (média), o que é otimista
   para quem acabou de subir. Aqui entra com a média dos ratings das
   equipas que desceram na época anterior, como no Elo.
=====================================================================
"""
import math

import pandas as pd

import configuracao as cfg


def golos_esperados(rating):
    """Diferença de golos esperada contra uma equipa média."""
    golos = cfg.PI_BASE ** (abs(rating) / cfg.PI_C) - 1
    return golos if rating >= 0 else -golos


def erro_comprimido(erro):
    return cfg.PI_C * math.log10(1 + erro)


def calcular_pi_ratings(jogos):
    """Devolve JogoID, PiCasa (rating em casa da equipa da casa),
    PiFora (rating fora da equipa de fora) e PiDifEsperada (diferença
    de golos esperada pelos pi-ratings), todos de ANTES do jogo."""
    jogos = jogos.sort_values(["Data", "Hora", "JogoID"], na_position="first")
    casa = {}                    # rating em casa de cada equipa
    fora = {}                    # rating fora de cada equipa
    equipas_anteriores = set()
    linhas = []

    for i, (epoca, jogos_epoca) in enumerate(jogos.groupby("Epoca", sort=False)):
        equipas = set(jogos_epoca["EquipaCasa"]) | set(jogos_epoca["EquipaFora"])

        if i == 0:
            for equipa in equipas:
                casa[equipa], fora[equipa] = 0.0, 0.0
        else:
            desceram = equipas_anteriores - equipas
            media_casa = sum(casa[e] for e in desceram) / len(desceram)
            media_fora = sum(fora[e] for e in desceram) / len(desceram)
            for equipa in equipas - equipas_anteriores:
                casa[equipa], fora[equipa] = media_casa, media_fora

        for jogo in jogos_epoca.itertuples():
            rating_casa, rating_fora = casa[jogo.EquipaCasa], fora[jogo.EquipaFora]
            esperada = golos_esperados(rating_casa) - golos_esperados(rating_fora)
            linhas.append({"JogoID": jogo.JogoID, "PiCasa": rating_casa,
                           "PiFora": rating_fora, "PiDifEsperada": esperada})
            if pd.isna(jogo.GolosCasa):
                continue

            real = jogo.GolosCasa - jogo.GolosFora
            ajuste = erro_comprimido(abs(real - esperada)) * cfg.PI_LAMBDA
            if real < esperada:          # a casa jogou abaixo do esperado
                ajuste = -ajuste

            casa[jogo.EquipaCasa] += ajuste
            fora[jogo.EquipaCasa] += ajuste * cfg.PI_GAMMA
            fora[jogo.EquipaFora] -= ajuste
            casa[jogo.EquipaFora] -= ajuste * cfg.PI_GAMMA

        equipas_anteriores = equipas

    return pd.DataFrame(linhas)