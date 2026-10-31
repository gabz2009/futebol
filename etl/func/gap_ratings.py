"""
=====================================================================
 GAP RATINGS (Wheatcroft, 2020 e 2021)
=====================================================================
 O QUE SÃO
   Ratings calculados com jogadas de ataque (remates, cantos) em vez
   de golos. Os golos têm muita sorte; os remates e os cantos mostram
   melhor quem dominou o jogo.

   Cada equipa tem 4 ratings, medidos na unidade da estatística
   (ex.: remates por jogo):
     - ataque em casa   (Ha)   - defesa em casa (Hd)
     - ataque fora      (Aa)   - defesa fora    (Ad)
   Na defesa, um valor ALTO quer dizer defesa FRACA (sofre muito).

 PREVISÃO DE UM JOGO (casa i contra fora j)
   esperado da casa = (Ha_i + Ad_j) / 2
   esperado de fora = (Aa_j + Hd_i) / 2

 ATUALIZAÇÃO DEPOIS DO JOGO (apêndice A do artigo de 2021)
   erro_casa = real da casa - esperado da casa
   erro_fora = real de fora - esperado de fora
   Equipa da casa i:
     Ha_i += LAMBDA * PHI1       * erro_casa
     Aa_i += LAMBDA * (1 - PHI1) * erro_casa
     Hd_i += LAMBDA * PHI1       * erro_fora
     Ad_i += LAMBDA * (1 - PHI1) * erro_fora
   Equipa de fora j:
     Aa_j += LAMBDA * PHI2       * erro_fora
     Ha_j += LAMBDA * (1 - PHI2) * erro_fora
     Ad_j += LAMBDA * PHI2       * erro_casa
     Hd_j += LAMBDA * (1 - PHI2) * erro_casa
   Nenhum rating desce abaixo de 0.

 COMEÇO E MUDANÇA DE ÉPOCA (como no artigo)
   - Primeira época dos dados: todos a 0 (a época de aquecimento
     serve para os ratings estabilizarem).
   - Os ratings continuam de uma época para a seguinte.
   - Uma equipa que sobe entra com a média das que desceram.

 SEM FUGA DE INFORMAÇÃO
   Guarda-se o esperado de ANTES do jogo. Os números reais do jogo
   só atualizam os ratings para os jogos seguintes.

 OS PARÂMETROS (LAMBDA, PHI1, PHI2) vêm de afinar_gap.py, que os
 escolhe minimizando o erro na previsão da estatística, só nas
 épocas de treino.
=====================================================================
"""
import pandas as pd

import configuracao as cfg

RATINGS = ["Ha", "Hd", "Aa", "Ad"]


def esperado_por_jogo(jogos, coluna_casa, coluna_fora, lam, phi1, phi2):
    """Para UMA estatística, devolve duas listas: o esperado da casa e o
    esperado de fora em cada jogo, pela ordem cronológica de 'jogos'.
    'jogos' tem de vir ordenado por data."""
    ratings = {}                     # equipa -> {"Ha": ..., "Hd": ..., "Aa": ..., "Ad": ...}
    equipas_anteriores = set()
    epoca_anterior = None
    esperado_casa, esperado_fora = [], []

    # Listas simples em vez de linhas do pandas: o ciclo fica muito mais rápido,
    # o que importa porque a afinação repete este cálculo centenas de vezes
    epocas = jogos["Epoca"].tolist()
    casas = jogos["EquipaCasa"].tolist()
    foras = jogos["EquipaFora"].tolist()
    reais_casa = jogos[coluna_casa].tolist()
    reais_fora = jogos[coluna_fora].tolist()

    for epoca, i, j, real_casa, real_fora in zip(epocas, casas, foras, reais_casa, reais_fora):
        if epoca != epoca_anterior:
            equipas = set(jogos.loc[jogos["Epoca"] == epoca, "EquipaCasa"]) | \
                      set(jogos.loc[jogos["Epoca"] == epoca, "EquipaFora"])
            if epoca_anterior is None:
                for equipa in equipas:
                    ratings[equipa] = {r: 0.0 for r in RATINGS}
            else:
                desceram = equipas_anteriores - equipas
                media = {r: sum(ratings[e][r] for e in desceram) / len(desceram) for r in RATINGS}
                for equipa in equipas - equipas_anteriores:
                    ratings[equipa] = dict(media)
            equipas_anteriores, epoca_anterior = equipas, epoca

        ri, rj = ratings[i], ratings[j]
        esp_casa = (ri["Ha"] + rj["Ad"]) / 2
        esp_fora = (rj["Aa"] + ri["Hd"]) / 2
        esperado_casa.append(esp_casa)
        esperado_fora.append(esp_fora)

        if pd.isna(real_casa) or pd.isna(real_fora):
            continue

        erro_casa = real_casa - esp_casa
        erro_fora = real_fora - esp_fora
        ri["Ha"] = max(ri["Ha"] + lam * phi1 * erro_casa, 0)
        ri["Aa"] = max(ri["Aa"] + lam * (1 - phi1) * erro_casa, 0)
        ri["Hd"] = max(ri["Hd"] + lam * phi1 * erro_fora, 0)
        ri["Ad"] = max(ri["Ad"] + lam * (1 - phi1) * erro_fora, 0)
        rj["Aa"] = max(rj["Aa"] + lam * phi2 * erro_fora, 0)
        rj["Ha"] = max(rj["Ha"] + lam * (1 - phi2) * erro_fora, 0)
        rj["Ad"] = max(rj["Ad"] + lam * phi2 * erro_casa, 0)
        rj["Hd"] = max(rj["Hd"] + lam * (1 - phi2) * erro_casa, 0)

    return esperado_casa, esperado_fora


def acrescentar_estatisticas(jogos):
    """Os remates falhados não vêm nos dados: são os remates menos os remates à baliza."""
    jogos = jogos.copy()
    jogos["RematesFalhadosCasa"] = jogos["RematesCasa"] - jogos["RematesBalizaCasa"]
    jogos["RematesFalhadosFora"] = jogos["RematesFora"] - jogos["RematesBalizaFora"]
    return jogos


def ordenar(jogos):
    return jogos.sort_values(["Data", "Hora", "JogoID"], na_position="first").reset_index(drop=True)


def calcular_gap(jogos):
    """Devolve JogoID e, para cada estatística de cfg.GAP_PARAMETROS,
    o esperado da casa, o esperado de fora e a diferença (antes do jogo)."""
    jogos = ordenar(acrescentar_estatisticas(jogos))
    resultado = pd.DataFrame({"JogoID": jogos["JogoID"]})
    for nome, p in cfg.GAP_PARAMETROS.items():
        casa, fora = esperado_por_jogo(jogos, p["casa"], p["fora"], p["lambda"], p["phi1"], p["phi2"])
        resultado[f"Gap{nome}Casa"] = casa
        resultado[f"Gap{nome}Fora"] = fora
        resultado[f"Gap{nome}Dif"] = resultado[f"Gap{nome}Casa"] - resultado[f"Gap{nome}Fora"]
    return resultado