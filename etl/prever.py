"""
=====================================================================
PREVISÕES DA ÉPOCA ATUAL
=====================================================================
 COMO CORRER (depois do ETL e das variáveis; o executar_tudo.py já o faz)
   python etl/prever.py

 O QUE FAZ
   1. Lê as variáveis (jogos jogados e por jogar), os jogos e o calendário.
   2. Prevê os 306 jogos da época atual com o modelo final (média
      geométrica da Ordinal, do Dixon-Coles e do boosting), treinado com
      todas as épocas anteriores e, no modo semanal, com os jogos da
      própria época já jogados antes de cada semana.
   3. Avalia os jogos já jogados da época atual contra as odds: é um
      teste novo, porque nenhum modelo os viu.
   4. Simula o resto da época 10 000 vezes: pontos esperados e
      probabilidades de título, Europa e descida de cada equipa.
   5. Calcula a classificação depois de cada jornada.
   6. Acrescenta ao histórico (dados/historico.db) as fotografias da
      simulação das jornadas que ainda lá não estão.
   7. Corre os controlos P01 a P03, S01 a S02 e H01 e grava as tabelas
      previsoes, simulacao_epoca, simulacao_posicoes, classificacao_jornada
      e qa_previsoes (para o Power BI).
=====================================================================
"""
import logging
import sqlite3
import sys
from contextlib import closing

import numpy as np
import pandas as pd

import configuracao as cfg
import func.avaliacao as av
import func.controlos as controlos
import func.guardar as guardar
import func.historico as historico
import func.previsao as previsao
import func.simulacao as simulacao
import func.calendario as calendario_mod

USO = previsao.USO


def configurar_log():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(cfg.PASTA_PROJETO / "dados" / "previsoes.log", mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    logging.captureWarnings(True)


def ler_tabelas():
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        variaveis = pd.read_sql("SELECT * FROM variaveis ORDER BY Data, JogoID", ligacao)
        jogos = pd.read_sql("SELECT JogoID, Epoca, Ficheiro, Data, EquipaCasa, EquipaFora, GolosCasa, GolosFora FROM jogos", ligacao, parse_dates=["Data"])
        calendario = pd.read_sql("SELECT * FROM calendario", ligacao)
        origem_calendario = pd.read_sql("SELECT * FROM origem_calendario", ligacao)
    so_api = calendario_mod.jogos_terminados_api(calendario, origem_calendario, jogos)
    jogos = pd.concat([jogos, so_api], ignore_index=True)
    return variaveis, jogos, calendario, origem_calendario


def avaliar_jogados(resultados, variaveis):
    """Os jogos já jogados da época atual: modelo final contra as odds (informativo)."""
    def odds(tipo):
        colunas = [f"ProbOdds{tipo}Casa", f"ProbOdds{tipo}Empate", f"ProbOdds{tipo}Fora"]
        return lambda treino, teste: teste[colunas].to_numpy()

    tabelas = {"Modelo final": resultados["Modelo final"],
               "Odds pré-jogo": av.walk_forward(variaveis, odds(""), USO),
               "Odds de fecho": av.walk_forward(variaveis, odds("Fecho"), USO)}
    com_odds = variaveis.loc[variaveis["ProbOddsCasa"].notna(), "JogoID"]
    jogados = {nome: t[t["Resultado"].notna() & t["JogoID"].isin(com_odds)].reset_index(drop=True) for nome, t in tabelas.items()}
    resumo = av.resumo(jogados)
    linhas = "; ".join(f"{r.Modelo}: log loss {r.LogLoss:.4f}, acerto {r.Acerto:.1%}" for r in resumo.itertuples())
    diferenca, minimo, maximo = av.comparar(jogados["Modelo final"], jogados["Odds pré-jogo"])
    controlos.registar("P03", "Jogos jogados da época atual: modelo final contra as odds (informativo)",
                       "-", len(jogados["Modelo final"]), "OK", False,
                       f"{linhas} | modelo final - odds pré-jogo: {diferenca:+.4f} [{minimo:+.4f}, {maximo:+.4f}]")

def avaliar_previsoes_reais(avaliacao):
    """P04 (informativo): as previsões oficiais desde cfg.INICIO_PREVISOES_REAIS (o teste em tempo real)."""
    reais = avaliacao[avaliacao["Resultado"].notna()]
    detalhe = "ainda sem jogos com resultado"
    if len(reais):
        detalhe = f"acerto {reais['Acerto'].mean():.1%}, log loss {reais['LogLoss'].mean():.4f}"
        com_odds = reais[reais["ProbOddsCasa"].notna()]          # os jogos só da API ainda não têm odds
        if len(com_odds):
            odds = av.medidas_por_jogo(com_odds[["ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]].to_numpy(),
                                       com_odds["Resultado"])
            detalhe += (f" | nos {len(com_odds)} jogos com odds: modelo {com_odds['LogLoss'].mean():.4f}, "
                        f"odds pré-jogo {odds['LogLoss'].mean():.4f}")
    controlos.registar("P04", f"Previsões reais (oficiais, desde {cfg.INICIO_PREVISOES_REAIS}): jogos com resultado",
                       "-", len(reais), "OK", False, detalhe)

def controlar(tabela, calendario):
    # P01: um jogo por linha, os mesmos jogos do calendário
    certos = len(tabela) == len(calendario) and set(tabela["JogoID"]) == set(calendario["JogoID"])
    controlos.registar("P01", "Uma previsão por cada jogo do calendário", len(calendario), len(tabela),
                       "OK" if certos else "FALHA", True)
    # P02: probabilidades entre 0 e 1 e a somar 1, no modelo final e em cada modelo
    colunas = [c for c in tabela.columns if c.startswith("Prob") and "Odds" not in c]
    valores = tabela[colunas].to_numpy()
    somas = [tabela[[f"ProbCasa{m}", f"ProbEmpate{m}", f"ProbFora{m}"]].sum(axis=1)
             for m in ["", "Ordinal", "DixonColes", "Boosting"]]
    erradas = int(((valores <= 0) | (valores >= 1)).any(axis=1).sum()
                  + sum(((s - 1).abs() > 1e-9).sum() for s in somas))
    controlos.registar("P02", "Probabilidades entre 0 e 1 e a somar 1 (modelo final e cada modelo)", 0, erradas,
                       "OK" if erradas == 0 else "FALHA", True)


def simular_epoca(tabela, calendario, origem_calendario):
    jogos_epoca = simulacao.preparar_jogos(tabela, simulacao.resultados_da_api(calendario, origem_calendario))
    classificacao = simulacao.classificacao_atual(jogos_epoca)
    por_jornada = simulacao.classificacao_por_jornada(jogos_epoca)
    equipas, pontos, posicoes = simulacao.simular(jogos_epoca)
    resumo = simulacao.resumir(equipas, pontos, posicoes, classificacao)
    por_posicao = simulacao.probabilidades_por_posicao(equipas, posicoes)
    logging.info(f"Simulação: {len(pontos)} simulações, {int((~jogos_epoca['Terminado']).sum())} jogos por jogar. "
                 + "; ".join(f"{r.Equipa} {r.ProbCampeao:.0%}" for r in resumo.nlargest(3, "ProbCampeao").itertuples()))

    # S01: em cada posição há exatamente uma equipa, e cada equipa acaba numa posição
    por_equipa = por_posicao.groupby("Equipa")["Probabilidade"].sum()
    por_lugar = por_posicao.groupby("Posicao")["Probabilidade"].sum()
    certas = np.allclose(por_equipa, 1) and np.allclose(por_lugar, 1)
    controlos.registar("S01", "Probabilidades por posição somam 1 (por equipa e por posição)", 0, int(not certas),
                       "OK" if certas else "FALHA", True)
    # S02: os pontos finais ficam entre os pontos atuais e o máximo possível
    jogos_falta = 2 * (len(equipas) - 1) - resumo["Jogos"]
    fora = ((resumo["PontosP10"] < resumo["Pontos"] - 1e-9) | (resumo["PontosP90"] > resumo["Pontos"] + 3 * jogos_falta)).sum()
    controlos.registar("S02", "Pontos simulados entre os pontos atuais e o máximo possível", 0, int(fora),
                       "OK" if fora == 0 else "FALHA", True)
    return resumo, por_posicao, por_jornada


def atualizar_historico(calendario, previsor_gb):
    """Fotografias da simulação depois de cada jornada (em dados/historico.db)."""
    with closing(sqlite3.connect(cfg.BASE_DADOS)) as ligacao:
        jogos = pd.read_sql("SELECT * FROM jogos", ligacao, parse_dates=["Data"])
        epocas = pd.read_sql("SELECT * FROM epocas", ligacao)
    total, novas = historico.atualizar(calendario, jogos, epocas, previsor_gb)
    controlos.registar("H01", "Histórico da simulação (historico.db): jornadas guardadas", "-", total, "OK", False,
                       f"acrescentadas agora: {novas}" if novas else "nenhuma jornada nova pronta")


def main():
    configurar_log()
    controlos.iniciar()
    logging.info("Início das previsões da época atual")

    variaveis, jogos, calendario, origem_calendario = ler_tabelas()
    resultados, previsor_gb = previsao.prever_epoca(variaveis, jogos)
    logging.info(f"Boosting, parâmetros escolhidos no início da época: {previsor_gb.escolhidos}")
    tabela = previsao.tabela_previsoes(resultados, calendario, variaveis, jogos)
    logging.info(f"Previsões: {len(tabela)} jogos ({int(tabela['Jogado'].sum())} jogados, "
                 f"{int((tabela['Jogado'] == 0).sum())} por jogar)")

    controlar(tabela, calendario)
    avaliar_jogados(resultados, variaveis)
    resumo, por_posicao, por_jornada = simular_epoca(tabela, calendario, origem_calendario)
    if controlos.ha_falhas_criticas():
        logging.error("Falha crítica nos controlos das previsões. Nada foi gravado.")
        sys.exit(1)
    atualizar_historico(calendario, previsor_gb)
    avaliacao = previsao.avaliar_oficiais(historico.ler_oficiais(), tabela)
    avaliar_previsoes_reais(avaliacao)

    guardar.substituir_tabelas({"previsoes": tabela, "simulacao_epoca": resumo, "simulacao_posicoes": por_posicao,
                                "classificacao_jornada": por_jornada, "avaliacao_oficial": avaliacao,
                                "qa_previsoes": controlos.tabela_controlos()},
                               cfg.BASE_DADOS, cfg.ESQUEMA_PREVISOES_SQL)

if __name__ == "__main__":
    main()