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
import func.boosting as gb
import func.dixon_coles as dc
import func.ordinal as ordinal
from func.variaveis import colunas_do_modelo

USO = "Previsão"



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

def prever_epoca(variaveis, jogos, previsor_gb=None):
    """Previsões dos jogos da época atual (uso "Previsão") com os três modelos e o modelo final.
    previsor_gb: um previsor do boosting já usado antes pode ser passado outra vez, para não
    voltar a escolher os parâmetros (a parte lenta). Devolve (resultados, previsor_gb)."""
    if previsor_gb is None:
        previsor_gb = gb.criar_previsor(colunas_do_modelo(variaveis))
    resultados = {
        "Ordinal": av.walk_forward(variaveis, semana_a_semana(ordinal.criar_previsor(cfg.COLUNAS_ORDINAL)), USO),
        "DixonColes": av.walk_forward(variaveis, dc.criar_previsor(jogos), USO),      # já se ajusta todas as semanas
        "Boosting": av.walk_forward(variaveis, semana_a_semana(previsor_gb), USO),
    }
    resultados["Modelo final"] = av.media_geometrica([resultados[m] for m in ["Ordinal", "DixonColes", "Boosting"]])
    return resultados, previsor_gb

def tabela_previsoes(resultados, calendario, variaveis, jogos=None):
    """resultados = {"Modelo final": ..., "Ordinal": ..., "DixonColes": ..., "Boosting": ...},
    tabelas do walk_forward da época atual. Devolve uma linha por jogo para o Power BI.
    jogos (opcional) = tabela jogos com os jogos só da API (calendario.jogos_terminados_api):
    acrescenta os golos e de onde veio o resultado (CSV ou API)."""
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
    if jogos is not None:
        tabela = tabela.merge(jogos[["JogoID", "GolosCasa", "GolosFora", "Ficheiro"]], on="JogoID", how="left", validate="one_to_one")
        tabela["FonteResultado"] = np.where(tabela["Resultado"].isna(), None, np.where(tabela["Ficheiro"] == "API", "API", "CSV"))
        tabela = tabela.drop(columns="Ficheiro")
    tabela["Jogado"] = tabela["Resultado"].notna().astype(int)
    tabela["Tipo"] = tipo_de_previsao(tabela)
    return tabela.sort_values(["Data", "Hora", "JogoID"]).reset_index(drop=True)

def avaliar_oficiais(oficiais, tabela):
    """As previsões oficiais (feitas no início de cada jornada e nunca recalculadas) com o
    resultado (do CSV ou da API) e as medidas. PrevisaoReal = 1 nos jogos a partir de
    cfg.INICIO_PREVISOES_REAIS: previstos com o modelo já fechado, o teste verdadeiro."""
    jogos = tabela[["JogoID", "Data", "Hora", "EquipaCasa", "EquipaFora", "Resultado", "FonteResultado",
                    "ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]]
    avaliacao = oficiais.merge(jogos, on="JogoID", how="left", validate="one_to_one")
    avaliacao = avaliacao[avaliacao["Data"] >= cfg.INICIO_PREVISOES_REAIS].reset_index(drop=True)
    medidas = av.medidas_por_jogo(avaliacao[["ProbCasa", "ProbEmpate", "ProbFora"]].to_numpy(), avaliacao["Resultado"])
    avaliacao[["Acerto", "LogLoss", "RPS"]] = medidas[["Acerto", "LogLoss", "RPS"]].to_numpy()
    return avaliacao.sort_values(["Data", "Hora", "JogoID"]).reset_index(drop=True)

def fora_de_ordem(tabela):
    """True nos jogos marcados para depois do início de uma jornada seguinte: é o que acontece a
    um jogo adiado quando volta a ter data (ex.: um jogo da jornada 11 remarcado para dezembro,
    quando a jornada 12 já começou em novembro)."""
    datas = pd.to_datetime(tabela["Data"])
    marcados = tabela["Estado"] != "POSTPONED"
    inicio = datas[marcados].groupby(tabela.loc[marcados, "Jornada"]).min().sort_index()
    # Para cada jornada, o primeiro dia de qualquer jornada A SEGUIR a ela
    inicio_seguinte = inicio[::-1].cummin()[::-1].shift(-1)
    return datas > tabela["Jornada"].map(inicio_seguinte)

def tipo_de_previsao(tabela):
    """Para que serve cada previsão:
    - Jogado: previsão da véspera de um jogo já jogado (serve para avaliar o modelo)
    - À espera de dados: a API dá-o como terminado mas ainda sem golos (raro: normalmente
      os golos vêm da API logo a seguir ao jogo; ver FonteResultado)
    - Adiado: adiado e ainda sem data nova
    - Remarcado: um jogo adiado que já tem data nova, depois de outras jornadas. Não conta
      para saber qual é a próxima jornada
    - Próxima jornada: a previsão "oficial", feita com tudo o que já se sabe
    - Provisória: jogos mais à frente. É a melhor estimativa de hoje e muda todas as
      semanas, à medida que os resultados entram. Serve sobretudo para a simulação da época."""
    adiado = (tabela["Jogado"] == 0) & (tabela["Estado"] == "POSTPONED")
    marcado = (tabela["Jogado"] == 0) & tabela["Estado"].isin(["SCHEDULED", "TIMED", "IN_PLAY", "PAUSED"])
    remarcado = marcado & fora_de_ordem(tabela)
    por_jogar = marcado & ~remarcado
    proxima = tabela.loc[por_jogar, "Jornada"].min()
    return np.select(
        [tabela["Jogado"] == 1, tabela["Estado"] == "FINISHED", adiado, remarcado,
         por_jogar & (tabela["Jornada"] == proxima)],
        ["Jogado", "À espera de dados", "Adiado", "Remarcado", "Próxima jornada"], default="Provisória")