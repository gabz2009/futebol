"""
=====================================================================
 RATING ELO
=====================================================================
 O QUE É
   Um número que mede a força de cada equipa (começa em 1500).
   Depois de cada jogo, quem ganha recebe pontos e quem perde cede
   os mesmos pontos. Quanto mais surpreendente o resultado, mais
   pontos mudam de mãos: ganhar ao líder vale mais do que ganhar ao
   último. É o mesmo sistema usado no xadrez.

 AS CONTAS DE UM JOGO
   1. Probabilidade esperada da equipa da casa:
        E = 1 / (1 + 10 ^ ((EloFora - (EloCasa + vantagem_casa)) / 400))
   2. Resultado real da casa: vitória = 1, empate = 0.5, derrota = 0.
   3. Mudança = K x (real - esperado). A casa ganha "mudança" pontos
      e a equipa de fora perde exatamente os mesmos.

 SEM FUGA DE INFORMAÇÃO
   O Elo guardado em cada jogo é o de ANTES do jogo. O resultado
   desse jogo só é usado para atualizar o rating para o jogo seguinte.

 ENTRE ÉPOCAS
   - Todas as equipas aproximam-se um pouco de 1500 (regressão à
     média): os plantéis mudam no verão.
   - Uma equipa que sobe entra com a média do Elo das equipas que
     desceram na época anterior. É uma estimativa razoável e só usa
     informação já conhecida no fim dessa época.
=====================================================================
"""
import pandas as pd

import configuracao as cfg


def probabilidade_esperada(elo_casa, elo_fora):
    diferenca = elo_fora - (elo_casa + cfg.ELO_VANTAGEM_CASA)
    return 1 / (1 + 10 ** (diferenca / 400))


def pontos_reais(resultado):
    return {"H": 1.0, "D": 0.5, "A": 0.0}[resultado]


def calcular_elo(jogos):
    """Devolve uma tabela com JogoID, EloCasa e EloFora (antes de cada jogo)."""
    jogos = jogos.sort_values(["Data", "Hora", "JogoID"], na_position="first")
    elo = {}                     # rating atual de cada equipa
    epoca_anterior = None
    equipas_anteriores = set()
    linhas = []

    for epoca, jogos_epoca in jogos.groupby("Epoca", sort=False):
        equipas = set(jogos_epoca["EquipaCasa"]) | set(jogos_epoca["EquipaFora"])

        if epoca_anterior is None:
            # Primeira época dos dados: todas começam iguais
            for equipa in equipas:
                elo[equipa] = cfg.ELO_INICIAL
        else:
            # Regressão à média das equipas que continuam
            for equipa in equipas & equipas_anteriores:
                elo[equipa] = elo[equipa] + cfg.ELO_REGRESSAO * (cfg.ELO_INICIAL - elo[equipa])
            # As que sobem entram com a média das que desceram
            desceram = equipas_anteriores - equipas
            elo_promovidas = sum(elo[e] for e in desceram) / len(desceram)
            for equipa in equipas - equipas_anteriores:
                elo[equipa] = elo_promovidas

        for jogo in jogos_epoca.itertuples():
            elo_casa, elo_fora = elo[jogo.EquipaCasa], elo[jogo.EquipaFora]
            linhas.append({"JogoID": jogo.JogoID, "EloCasa": elo_casa, "EloFora": elo_fora})
            if pd.isna(jogo.Resultado):
                continue

            mudanca = cfg.ELO_K * (pontos_reais(jogo.Resultado) - probabilidade_esperada(elo_casa, elo_fora))
            elo[jogo.EquipaCasa] = elo_casa + mudanca
            elo[jogo.EquipaFora] = elo_fora - mudanca

        epoca_anterior = epoca
        equipas_anteriores = equipas

    return pd.DataFrame(linhas)