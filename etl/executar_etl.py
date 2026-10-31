"""
=====================================================================
 ETL - LIGA PORTUGAL (FASE 1)
=====================================================================
 COMO CORRER
   python etl/executar_etl.py

 O QUE FAZ, POR ORDEM
   1. Lê os CSV de dados/origem (um por época).
   2. Uniformiza as colunas e junta tudo numa só tabela.
   3. Corre os controlos de qualidade.
   4. Se não houver falhas críticas, recria dados/futebol.db com:
        - origem_jogos:     os CSV tal como vieram (dados brutos)
        - jogos:            um jogo por linha, todas as épocas (dados tratados)
        - equipas:          uma linha por equipa
        - epocas:           uma linha por época, com o uso no modelo
        - qa_controlos:     resultado de cada controlo
        - qa_odds_em_falta: jogos com alguma odd vazia
        - etl_execucoes:    histórico de todas as execuções
   Se houver falhas críticas, PÁRA antes de gravar: a base de dados
   anterior fica como estava e só se acrescenta a falha ao histórico.
=====================================================================
"""
import logging
import sys
from datetime import datetime

import pandas as pd

import configuracao as cfg
import func.controlos as controlos
import func.guardar as guardar
import func.ler_dados as ler_dados
import func.uniformizar as uniformizar
import func.calendario as calendario_mod

# Informação da execução atual, preenchida ao longo do processo
execucao = {"Inicio": None, "Fim": None, "Estado": None, "Ficheiros": None,
            "JogosLidos": None, "JogosGravados": None, "Mensagem": None}


def configurar_log():
    cfg.FICHEIRO_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(cfg.FICHEIRO_LOG, mode="w", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    # Os avisos do pandas (warnings) também passam a ir para o etl.log
    logging.captureWarnings(True)


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parar_se_houver_falhas(momento):
    if controlos.ha_falhas_criticas():
        execucao.update(Fim=agora(), Estado="FALHA", JogosGravados=0,
                        Mensagem=f"Falha crítica {momento}")
        guardar.registar_falha(cfg.BASE_DADOS, execucao)
        logging.error(f"Falha crítica {momento}. Nada foi gravado. Ver {cfg.FICHEIRO_LOG}")
        sys.exit(1)


def main():
    configurar_log()
    controlos.iniciar()
    execucao["Inicio"] = agora()
    logging.info("Início do ETL")

    # 1. Ler
    tabelas = ler_dados.ler_todos()
    execucao["Ficheiros"] = len(tabelas)
    execucao["JogosLidos"] = sum(len(t) for t in tabelas.values())
    controlos.controlo_ficheiros(tabelas)
    parar_se_houver_falhas("na leitura dos ficheiros")
    origem = ler_dados.juntar_origem(tabelas)

    # 2. Uniformizar e juntar
    jogos, colunas_em_falta = uniformizar.juntar_epocas(tabelas)
    controlos.controlo_colunas(colunas_em_falta)
    parar_se_houver_falhas("nas colunas")

    jogos = uniformizar.converter_tipos(jogos)
    jogos = uniformizar.acrescentar_colunas(jogos)
    equipas = uniformizar.criar_equipas(jogos)
    epocas = uniformizar.criar_epocas(jogos)

    # 3. Controlos
    controlos.controlo_jogos_por_epoca(jogos)
    controlos.controlo_jogos_por_equipa(jogos)
    controlos.controlo_repetidos(jogos)
    controlos.controlo_valores_obrigatorios(jogos)
    controlos.controlo_coerencia(jogos)
    controlos.controlo_datas(jogos)
    odds_em_falta = controlos.controlo_odds(jogos)
    controlos.controlo_linhas(tabelas, jogos)
    controlos.controlo_odds_plausiveis(jogos)
    controlos.controlo_hora(jogos)
    controlos.controlo_nomes_equipas(equipas)
    parar_se_houver_falhas("nos controlos de qualidade")

    controlos.controlo_ficheiro_calendario()
    parar_se_houver_falhas("na leitura do calendário")
    origem_calendario, descarregado_em = calendario_mod.ler_calendario(cfg.FICHEIRO_CALENDARIO)
    logging.info(f"Calendário: {len(origem_calendario)} jogos, descarregado em {descarregado_em}")
    controlos.controlo_nomes_calendario(origem_calendario)
    parar_se_houver_falhas("nos nomes do calendário")
    calendario = calendario_mod.criar_calendario(origem_calendario)
    controlos.controlo_calendario_completo(calendario)
    controlos.controlo_calendario_e_jogos(calendario, origem_calendario, jogos)
    parar_se_houver_falhas("no calendário")

    # 4. Gravar
    execucao.update(Fim=agora(), Estado="OK", JogosGravados=len(jogos),
                    Mensagem=f"{len(jogos)} jogos de {jogos['Epoca'].nunique()} épocas")
    historico = pd.concat([guardar.ler_execucoes_anteriores(cfg.BASE_DADOS),
                           pd.DataFrame([execucao])], ignore_index=True)

    # A ordem conta: equipas e epocas antes de jogos, por causa das chaves estrangeiras
    guardar.gravar_tabelas({
        "equipas": equipas,
        "epocas": epocas,
        "jogos": jogos,
        "origem_jogos": origem,
        "qa_controlos": controlos.tabela_controlos(),
        "qa_odds_em_falta": odds_em_falta,
        "etl_execucoes": historico,
        "origem_calendario": origem_calendario,
        "calendario": calendario
    }, cfg.BASE_DADOS, cfg.ESQUEMA_SQL)

    logging.info(f"ETL concluído: {execucao['Mensagem']} e {len(equipas)} equipas")


if __name__ == "__main__":
    main()