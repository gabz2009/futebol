"""
=====================================================================
 TESTES DA VERIFICAÇÃO DO CSV DESCARREGADO
=====================================================================
"""
import func.descarregar as descarregar

CABECALHO = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
JOGO = "P1,08/08/2026,20:15,Benfica,Porto,2,1,H\n"


def test_csv_bom_e_aceite():
    tabela, motivo = descarregar.validar_csv(("\ufeff" + CABECALHO + JOGO * 3).encode("utf-8"), 2)
    assert motivo is None and len(tabela) == 3


def test_pagina_de_erro_em_vez_de_csv_e_recusada():
    tabela, motivo = descarregar.validar_csv(b"<html><body>Not found</body></html>", 0)
    assert tabela is None and "colunas" in motivo


def test_csv_com_menos_jogos_do_que_o_atual_e_recusado():
    # O atual tem 72 jogos; o novo chegou cortado com 3
    tabela, motivo = descarregar.validar_csv((CABECALHO + JOGO * 3).encode("utf-8"), 72)
    assert tabela is None and "incompleto" in motivo


def test_linhas_vazias_no_fim_nao_contam():
    tabela, _ = descarregar.validar_csv((CABECALHO + JOGO * 2 + ",,,,,,,\n,,,,,,,\n").encode("utf-8"), 0)
    assert len(tabela) == 2