"""
=====================================================================
 CONTROLOS DAS VARIÁVEIS (FASE 2)
=====================================================================
 Usam o mesmo registo dos controlos do ETL (controlos.registar),
 com códigos V01, V02... e vão para a tabela qa_variaveis.

 O MAIS IMPORTANTE É O V04, O TESTE ANTI-FUGA:
   Altera-se por completo o resultado e as estatísticas de alguns
   jogos e voltam-se a calcular as variáveis. As variáveis DESSES
   jogos não podem mudar (só usam jogos anteriores). As dos jogos
   SEGUINTES das mesmas equipas têm de mudar (senão o teste não
   estaria a testar nada).
=====================================================================
"""
import numpy as np
import pandas as pd

import configuracao as cfg
import func.variaveis as variaveis_mod
from func.controlos import registar


def controlo_uma_linha_por_jogo(variaveis, jogos):
    ok = len(variaveis) == len(jogos) and variaveis["JogoID"].is_unique
    registar("V01", "Uma linha por jogo e JogoID único", len(jogos), len(variaveis),
             "OK" if ok else "FALHA", True)


def controlo_sem_vazios(variaveis):
    # Fora da época de aquecimento, nenhuma variável pode ficar vazia
    colunas = variaveis_mod.colunas_do_modelo(variaveis)
    usadas = variaveis[variaveis["Uso"] != "Aquecimento"]
    vazios = usadas[colunas].isna().sum()
    vazios = vazios[vazios > 0]
    detalhe = "; ".join(f"{c}: {n}" for c, n in vazios.items())
    registar("V02", "Sem variáveis vazias fora da época de aquecimento", 0, int(vazios.sum()),
             "OK" if vazios.empty else "FALHA", True, detalhe)


def controlo_probabilidades(variaveis):
    soma = variaveis[["ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]].sum(axis=1, min_count=3)
    erradas = int(((soma - 1).abs() > 1e-9).sum())
    sem_odds = int(soma.isna().sum())
    registar("V03", "Probabilidades das odds somam 1", 0, erradas,
             "OK" if erradas == 0 else "FALHA", True, f"jogos sem odds: {sem_odds}")


def alterar_jogo(jogos, jogo_id):
    """Inverte por completo um jogo: golos trocados (+5), resultado e remates."""
    alterados = jogos.copy()
    linha = alterados["JogoID"] == jogo_id
    alterados.loc[linha, ["GolosCasa", "GolosFora"]] = alterados.loc[linha, ["GolosFora", "GolosCasa"]].values + 5
    alterados.loc[linha, "Resultado"] = np.where(alterados.loc[linha, "Resultado"] == "H", "A", "H")
    alterados.loc[linha, ["RematesBalizaCasa", "RematesBalizaFora"]] = 20
    return alterados


def controlo_anti_fuga(jogos, epocas, variaveis, calcular_elo):
    # Um jogo a meio de cada época (o 150.º por data).
    # Altera-se UM jogo de cada vez: se se alterassem todos juntos, um
    # jogo alterado em 2018 mudava o Elo dos jogos alterados em 2023,
    # e o teste acusava uma fuga que não existe.
    jogos = jogos.sort_values(["Data", "JogoID"])
    alvo = jogos.groupby("Epoca").nth(150)["JogoID"].tolist()
    colunas = variaveis_mod.colunas_do_modelo(variaveis)
    originais = variaveis.set_index("JogoID")[colunas]

    mudaram_alvo, mudaram_seguintes, total_seguintes = [], 0, 0
    for jogo_id in alvo:
        alterados = alterar_jogo(jogos, jogo_id)
        novas = variaveis_mod.criar_variaveis(alterados, calcular_elo(alterados), epocas).set_index("JogoID")[colunas]

        # 1) As variáveis do próprio jogo não podem mudar
        if not np.isclose(originais.loc[jogo_id], novas.loc[jogo_id], equal_nan=True).all():
            mudaram_alvo.append(jogo_id)

        # 2) O jogo seguinte da equipa da casa TEM de mudar
        jogo = jogos[jogos["JogoID"] == jogo_id].iloc[0]
        seguinte = jogos[(jogos["Data"] > jogo["Data"]) & (jogos["EquipaCasa"] == jogo["EquipaCasa"])]
        if not seguinte.empty:
            total_seguintes += 1
            seguinte_id = seguinte.iloc[0]["JogoID"]
            if not np.isclose(originais.loc[seguinte_id], novas.loc[seguinte_id], equal_nan=True).all():
                mudaram_seguintes += 1

    ok = not mudaram_alvo and mudaram_seguintes == total_seguintes
    registar("V04", "Anti-fuga: alterar um jogo não muda as suas variáveis, só as dos jogos seguintes",
             0, len(mudaram_alvo), "OK" if ok else "FALHA", True,
             f"jogos testados: {len(alvo)}; jogos seguintes que mudaram: {mudaram_seguintes} de {total_seguintes}"
             + (f"; com fuga: {mudaram_alvo}" if mudaram_alvo else ""))


def controlo_elo(variaveis):
    # Informativo: a média do Elo de cada época deve andar perto de 1500
    medias = pd.concat([variaveis.groupby("Epoca")["EloCasa"].mean(),
                        variaveis.groupby("Epoca")["EloFora"].mean()], axis=1).mean(axis=1)
    desvio = float((medias - cfg.ELO_INICIAL).abs().max())
    registar("V05", "Média do Elo por época perto de 1500 (desvio máximo)", "< 25", round(desvio, 1),
             "OK" if desvio < 25 else "AVISO", False)