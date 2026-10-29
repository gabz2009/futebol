"""
=====================================================================
 FASE 2 - VARIÁVEIS DE CADA JOGO
=====================================================================
 A REGRA DE OURO
   Cada variável de um jogo só pode usar informação conhecida ANTES
   desse jogo começar. Nunca os golos, remates ou o resultado do
   próprio jogo (isso seria fuga de informação).

 COMO SE FAZ
   1. Tabela por equipa e jogo: cada jogo dá duas linhas, uma do
      ponto de vista de cada equipa (golos marcados, sofridos...).
      Assim as contas são iguais para a casa e para fora.
   2. Médias dos últimos jogos com shift(1): o shift empurra os
      valores uma linha para baixo, por isso a média de um jogo
      só vê os jogos anteriores.
   3. Volta-se a uma linha por jogo, com as variáveis da casa, as
      de fora e as diferenças entre as duas.

 EQUIPAS SEM HISTÓRICO
   - As médias continuam de uma época para a seguinte quando a
     equipa jogou as duas épocas seguidas.
   - Uma equipa que sobe começa do zero. No primeiro jogo, como
     ainda não há jogos dela, usa-se a média das equipas que
     desceram na época anterior (as equipas que ela substitui).
   - Na primeira época dos dados (aquecimento) ninguém tem
     histórico, por isso essa época não entra no treino.
=====================================================================
"""
import pandas as pd

import configuracao as cfg

# Estatísticas de cada jogo, do ponto de vista de uma equipa
ESTATISTICAS = ["Pontos", "GolosMarcados", "GolosSofridos", "RematesBaliza", "RematesBalizaSofridos"]

# Nome das variáveis de forma: médias dos últimos JANELA_FORMA jogos
FORMA = {estatistica: f"{estatistica}Ult{cfg.JANELA_FORMA}" for estatistica in ESTATISTICAS}

# Variáveis por equipa que passam para a tabela final
VARIAVEIS_EQUIPA = list(FORMA.values()) + ["PontosLocal", "DiasDescanso", "JogosNaEpoca", "Promovida"]


def criar_tabela_equipa_jogo(jogos):
    """Duas linhas por jogo: uma para a equipa da casa e outra para a de fora."""
    comum = jogos[["JogoID", "Epoca", "Data", "Hora"]]
    casa = comum.assign(
        Equipa=jogos["EquipaCasa"], Adversario=jogos["EquipaFora"], Local="Casa",
        GolosMarcados=jogos["GolosCasa"], GolosSofridos=jogos["GolosFora"],
        RematesBaliza=jogos["RematesBalizaCasa"], RematesBalizaSofridos=jogos["RematesBalizaFora"])
    fora = comum.assign(
        Equipa=jogos["EquipaFora"], Adversario=jogos["EquipaCasa"], Local="Fora",
        GolosMarcados=jogos["GolosFora"], GolosSofridos=jogos["GolosCasa"],
        RematesBaliza=jogos["RematesBalizaFora"], RematesBalizaSofridos=jogos["RematesBalizaCasa"])

    equipa_jogo = pd.concat([casa, fora], ignore_index=True)
    diferenca = equipa_jogo["GolosMarcados"] - equipa_jogo["GolosSofridos"]
    equipa_jogo["Pontos"] = (diferenca > 0) * 3 + (diferenca == 0) * 1

    # Ordem cronológica dentro de cada equipa: é a base de todas as médias
    return equipa_jogo.sort_values(["Equipa", "Data", "Hora", "JogoID"], na_position="first").reset_index(drop=True)


def marcar_blocos(equipa_jogo):
    """Um bloco = épocas seguidas de uma equipa na Primeira Liga.
    Se a equipa falha uma época (desceu), o histórico recomeça."""
    ordem = {epoca: i for i, epoca in enumerate(cfg.EPOCAS_ESPERADAS)}
    equipa_jogo = equipa_jogo.copy()
    indice = equipa_jogo["Epoca"].map(ordem)

    # Para cada linha: a época anterior desta equipa nos dados
    epocas_equipa = equipa_jogo[["Equipa", "Epoca"]].drop_duplicates()
    epocas_equipa["Indice"] = epocas_equipa["Epoca"].map(ordem)
    epocas_equipa["IndiceAnterior"] = epocas_equipa.groupby("Equipa")["Indice"].shift(1)
    # Novo bloco quando não há época anterior ou quando a anterior não é a imediatamente antes
    epocas_equipa["NovoBloco"] = epocas_equipa["IndiceAnterior"] != epocas_equipa["Indice"] - 1
    epocas_equipa["Bloco"] = epocas_equipa.groupby("Equipa")["NovoBloco"].cumsum()
    # Promovida: chegou nesta época e não é a primeira época dos dados
    epocas_equipa["Promovida"] = (epocas_equipa["NovoBloco"] & (epocas_equipa["Indice"] > 0)).astype(int)

    equipa_jogo = equipa_jogo.merge(epocas_equipa[["Equipa", "Epoca", "Bloco", "Promovida"]],
                                    on=["Equipa", "Epoca"], how="left", validate="many_to_one")
    assert indice.notna().all(), "Há épocas que não estão em EPOCAS_ESPERADAS"
    return equipa_jogo


def media_dos_anteriores(serie, janela):
    # shift(1): o jogo atual nunca entra na sua própria média
    return serie.shift(1).rolling(janela, min_periods=1).mean()


def calcular_forma(equipa_jogo):
    equipa_jogo = equipa_jogo.copy()
    grupos = equipa_jogo.groupby(["Equipa", "Bloco"])
    for estatistica, variavel in FORMA.items():
        equipa_jogo[variavel] = grupos[estatistica].transform(media_dos_anteriores, cfg.JANELA_FORMA)

    # Forma só no mesmo local: os jogos em casa da equipa da casa
    # e os jogos fora da equipa de fora
    equipa_jogo["PontosLocal"] = (equipa_jogo.groupby(["Equipa", "Bloco", "Local"])["Pontos"]
                                  .transform(media_dos_anteriores, cfg.JANELA_FORMA))

    # Jogos já feitos nesta época, antes deste (0 no primeiro jogo)
    equipa_jogo["JogosNaEpoca"] = equipa_jogo.groupby(["Equipa", "Epoca"]).cumcount()

    # Dias desde o último jogo do campeonato da mesma época
    dias = equipa_jogo.groupby(["Equipa", "Epoca"])["Data"].diff().dt.days
    equipa_jogo["DiasDescanso"] = dias.fillna(cfg.DESCANSO_MAX).clip(upper=cfg.DESCANSO_MAX).astype(int)
    return equipa_jogo


def preencher_inicio_promovidas(equipa_jogo):
    """No primeiro jogo de uma equipa promovida não há médias.
    Usa-se a média, por jogo, das equipas que desceram na época anterior."""
    equipa_jogo = equipa_jogo.copy()
    epocas = cfg.EPOCAS_ESPERADAS
    variaveis = list(FORMA.values()) + ["PontosLocal"]

    for i in range(1, len(epocas)):
        anterior, atual = epocas[i - 1], epocas[i]
        equipas_anterior = set(equipa_jogo.loc[equipa_jogo["Epoca"] == anterior, "Equipa"])
        equipas_atual = set(equipa_jogo.loc[equipa_jogo["Epoca"] == atual, "Equipa"])
        desceram = equipas_anterior - equipas_atual
        if not desceram:
            continue

        jogos_desceram = equipa_jogo[(equipa_jogo["Epoca"] == anterior) & equipa_jogo["Equipa"].isin(desceram)]
        medias = {FORMA[e]: jogos_desceram[e].mean() for e in ESTATISTICAS}
        medias["PontosLocal"] = jogos_desceram["Pontos"].mean()

        promovidas = (equipa_jogo["Epoca"] == atual) & (equipa_jogo["Promovida"] == 1)
        for variavel in variaveis:
            vazio = promovidas & equipa_jogo[variavel].isna()
            equipa_jogo.loc[vazio, variavel] = medias[variavel]
    return equipa_jogo


def probabilidades_odds(jogos):
    """Converte as odds em probabilidades e tira a margem da casa de apostas.
    Usa a Bet365 e, se faltar, a média do mercado.
    Servem para COMPARAR com o modelo no fim, não para o treinar."""
    resultado = pd.DataFrame({"JogoID": jogos["JogoID"]})
    for sufixo, coluna in [("Casa", "OddCasa"), ("Empate", "OddEmpate"), ("Fora", "OddFora")]:
        resultado[sufixo] = 1 / jogos[f"{coluna}B365"].fillna(jogos[f"{coluna}Media"])
    soma = resultado[["Casa", "Empate", "Fora"]].sum(axis=1, min_count=3)
    for sufixo in ["Casa", "Empate", "Fora"]:
        resultado[f"ProbOdds{sufixo}"] = resultado[sufixo] / soma
    return resultado[["JogoID", "ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]]


def criar_variaveis(jogos, elo, pi, epocas):
    """Junta tudo numa linha por jogo: casa, fora, diferenças, Elo, odds e o resultado."""
    equipa_jogo = criar_tabela_equipa_jogo(jogos)
    equipa_jogo = marcar_blocos(equipa_jogo)
    equipa_jogo = calcular_forma(equipa_jogo)
    equipa_jogo = preencher_inicio_promovidas(equipa_jogo)

    casa = equipa_jogo[equipa_jogo["Local"] == "Casa"].set_index("JogoID")[VARIAVEIS_EQUIPA].add_prefix("Casa")
    fora = equipa_jogo[equipa_jogo["Local"] == "Fora"].set_index("JogoID")[VARIAVEIS_EQUIPA].add_prefix("Fora")

    variaveis = (jogos[["JogoID", "Epoca", "Data", "EquipaCasa", "EquipaFora", "EpocaCOVID"]]
                 .merge(casa, on="JogoID", how="left", validate="one_to_one")
                 .merge(fora, on="JogoID", how="left", validate="one_to_one")
                 .merge(elo, on="JogoID", how="left", validate="one_to_one")
                 .merge(pi, on="JogoID", how="left", validate="one_to_one"))

    # Diferenças casa - fora: muitas vezes é o que o modelo mais aproveita
    for variavel in list(FORMA.values()) + ["PontosLocal", "DiasDescanso"]:
        variaveis[f"Dif{variavel}"] = variaveis[f"Casa{variavel}"] - variaveis[f"Fora{variavel}"]
    variaveis["DifElo"] = variaveis["EloCasa"] - variaveis["EloFora"]
    variaveis["EquilibrioElo"] = variaveis["DifElo"].abs()
    variaveis["EquilibrioPi"] = variaveis["PiDifEsperada"].abs()

    variaveis = variaveis.merge(probabilidades_odds(jogos), on="JogoID", how="left", validate="one_to_one")
    variaveis = variaveis.merge(epocas[["Epoca", "Uso"]], on="Epoca", how="left", validate="many_to_one")

    # O alvo: o que o modelo vai aprender a prever (fica no fim, separado)
    variaveis = variaveis.merge(jogos[["JogoID", "Resultado"]], on="JogoID", how="left", validate="one_to_one")
    return variaveis.sort_values(["Data", "JogoID"]).reset_index(drop=True)


def colunas_do_modelo(variaveis):
    """As colunas que o modelo pode usar: tudo menos identificação, odds e resultado."""
    excluir = {"JogoID", "Epoca", "Data", "EquipaCasa", "EquipaFora", "Uso", "Resultado",
               "ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora", "CasaJogosNaEpoca",
               "ForaJogosNaEpoca", "EpocaCOVID", "CasaDiasDescanso", "ForaDiasDescanso", "DifDiasDescanso"}
    return [c for c in variaveis.columns if c not in excluir]