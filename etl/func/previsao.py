"""
=====================================================================
 PREVISÕES DA ÉPOCA ATUAL (FASE 7)
=====================================================================
 MODO SEMANAL
   Os ratings (Elo, pi, GAP, forma) já mudam depois de cada jogo. Aqui
   também os PESOS dos modelos (Ordinal e boosting) voltam a ser
   treinados todas as semanas, com todos os jogos já jogados antes
   dessa semana, incluindo os da própria época.
   Cada jogo jogado é assim previsto como na véspera: só com o que
   se sabia nesse dia. Os jogos por jogar são previstos com tudo o
   que já se jogou.

   Semanas sem jogos novos (por exemplo, todas as semanas futuras)
   têm o mesmo treino: juntam-se e o modelo é treinado uma só vez.

 TABELA PARA O POWER BI (previsoes)
   Um jogo por linha, com as probabilidades do modelo final e de cada
   modelo, as das odds (só nos jogos já com odds) e, nos jogos jogados,
   o resultado e as medidas.
=====================================================================
"""
import numpy as np
import pandas as pd

import configuracao as cfg
import func.avaliacao as av


def semana_a_semana(previsor):
    """Recebe um previsor(treino, teste) e devolve outro que treina de novo todas as semanas.
    'treino' = épocas anteriores; os jogos já jogados de 'teste' entram no treino das
    semanas seguintes."""
    def previsor_semanal(treino, teste):
        teste = teste.reset_index(drop=True)
        datas = pd.to_datetime(teste["Data"])
        semana = (datas - datas.min()).dt.days // 7
        inicio_semana = datas.groupby(semana).transform("min")
        jogados = teste[teste["Resultado"].notna()]
        datas_jogados = pd.to_datetime(jogados["Data"])
        # Quantos jogos da própria época já se conheciam no início de cada semana.
        # Semanas com o mesmo número têm o mesmo treino: o modelo é treinado uma só vez.
        conhecidos = inicio_semana.map(lambda dia: int((datas_jogados < dia).sum()))

        probabilidades = np.zeros((len(teste), 3))
        for _, linhas in teste.groupby(conhecidos).groups.items():
            inicio = inicio_semana[linhas].min()
            treino_semana = pd.concat([treino, jogados[datas_jogados < inicio]], ignore_index=True)
            probabilidades[linhas] = previsor(treino_semana, teste.loc[linhas])
        return probabilidades

    return previsor_semanal


def tabela_previsoes(resultados, calendario, variaveis):
    """resultados = {"Modelo final": ..., "Ordinal": ..., "DixonColes": ..., "Boosting": ...},
    tabelas do walk_forward da época atual. Devolve uma linha por jogo para o Power BI."""
    final = resultados["Modelo final"]
    tabela = final[["JogoID", "Epoca", "Resultado", "ProbH", "ProbD", "ProbA", "Acerto", "LogLoss", "RPS"]].rename(
        columns={"ProbH": "ProbCasa", "ProbD": "ProbEmpate", "ProbA": "ProbFora"})
    # O resultado mais provável para o modelo final
    tabela["Previsto"] = np.array(cfg.RESULTADOS_VALIDOS)[final[["ProbH", "ProbD", "ProbA"]].to_numpy().argmax(axis=1)]
    # As probabilidades de cada modelo que entra no modelo final (ex.: ProbCasaOrdinal)
    for nome, r in resultados.items():
        if nome != "Modelo final":
            for coluna, sufixo in [("ProbH", "Casa"), ("ProbD", "Empate"), ("ProbA", "Fora")]:
                tabela[f"Prob{sufixo}{nome}"] = r[coluna].to_numpy()

    # Data, hora e jornada do calendário (as datas reais, não as dos cálculos)
    tabela = tabela.merge(calendario[["JogoID", "Jornada", "Data", "Hora", "EquipaCasa", "EquipaFora", "Estado"]],
                          on="JogoID", how="left", validate="one_to_one")
    odds = variaveis[["JogoID", "ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora",
                      "ProbOddsFechoCasa", "ProbOddsFechoEmpate", "ProbOddsFechoFora"]]
    tabela = tabela.merge(odds, on="JogoID", how="left", validate="one_to_one")
    tabela["Jogado"] = tabela["Resultado"].notna().astype(int)
    tabela["Tipo"] = tipo_de_previsao(tabela)
    return tabela.sort_values(["Data", "Hora", "JogoID"]).reset_index(drop=True)

def tipo_de_previsao(tabela):
    """Para que serve cada previsão:
    - Jogado: previsão da véspera de um jogo já jogado (serve para avaliar o modelo)
    - À espera de dados: a API já o dá como terminado, mas ainda não está no CSV
    - Próxima jornada: a previsão "oficial", feita com tudo o que já se sabe
    - Provisória: jogos mais à frente. É a melhor estimativa de hoje e muda todas as
      semanas, à medida que os resultados entram. Serve sobretudo para a simulação da época."""
    por_jogar = (tabela["Jogado"] == 0) & tabela["Estado"].isin(["SCHEDULED", "TIMED", "IN_PLAY", "PAUSED"])
    proxima = tabela.loc[por_jogar, "Jornada"].min()
    return np.select(
        [tabela["Jogado"] == 1, tabela["Estado"] == "FINISHED", por_jogar & (tabela["Jornada"] == proxima)],
        ["Jogado", "À espera de dados", "Próxima jornada"], default="Provisória")