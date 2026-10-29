"""
=====================================================================
 TESTES DOS CONTROLOS
=====================================================================
 PORQUE EXISTEM?
   Um controlo que nunca falha pode estar avariado. Estes testes dão
   aos controlos dados PROPOSITADAMENTE errados e confirmam que eles
   dão FALHA. Também confirmam que dados certos dão OK.

 COMO CORRER (na pasta do projeto)
   python -m pytest
=====================================================================
"""
import pandas as pd

import func.controlos as controlos


def jogo(**alteracoes):
    """Um jogo válido (Benfica 2-1 Porto a 10/08/2021). Muda-se só o que o teste precisa."""
    base = {
        "JogoID": "21-22_Benfica_Porto", "Epoca": "21-22", "Ficheiro": "P1_21-22.csv",
        "Data": pd.Timestamp("2021-08-10"), "Hora": "20:15",
        "EquipaCasa": "Benfica", "EquipaFora": "Porto",
        "GolosCasa": 2, "GolosFora": 1, "Resultado": "H",
        "GolosCasaIntervalo": 1, "GolosForaIntervalo": 0,
        "RematesCasa": 12, "RematesFora": 8, "RematesBalizaCasa": 5, "RematesBalizaFora": 3,
        "OddCasaB365": 2.10, "OddEmpateB365": 3.40, "OddForaB365": 3.50,
        "OddCasaMedia": 2.05, "OddEmpateMedia": 3.35, "OddForaMedia": 3.45,
        "OddCasaFechoB365": 2.05, "OddEmpateFechoB365": 3.45, "OddForaFechoB365": 3.55,
        "OddCasaFechoMedia": 2.00, "OddEmpateFechoMedia": 3.40, "OddForaFechoMedia": 3.50
    }
    base.update(alteracoes)
    return base


def estado_do_ultimo(funcao, *dados):
    controlos.iniciar()
    funcao(*dados)
    return controlos.controlos[-1]["Estado"]


# ---------- dados certos: tudo OK ----------

def test_jogo_valido_passa_em_todos():
    jogos = pd.DataFrame([jogo()])
    assert estado_do_ultimo(controlos.controlo_repetidos, jogos) == "OK"
    assert estado_do_ultimo(controlos.controlo_coerencia, jogos) == "OK"
    assert estado_do_ultimo(controlos.controlo_datas, jogos) == "OK"
    assert estado_do_ultimo(controlos.controlo_odds_plausiveis, jogos) == "OK"


# ---------- dados errados: cada controlo tem de falhar ----------

def test_c05_apanha_jogo_repetido():
    jogos = pd.DataFrame([jogo(), jogo()])
    assert estado_do_ultimo(controlos.controlo_repetidos, jogos) == "FALHA"


def test_c07_apanha_resultado_que_nao_bate_com_os_golos():
    jogos = pd.DataFrame([jogo(Resultado="A")])            # 2-1 mas diz vitória fora
    assert estado_do_ultimo(controlos.controlo_coerencia, jogos) == "FALHA"


def test_c07_apanha_golos_ao_intervalo_acima_dos_finais():
    jogos = pd.DataFrame([jogo(GolosCasaIntervalo=3)])     # 3 ao intervalo, 2 no fim
    assert estado_do_ultimo(controlos.controlo_coerencia, jogos) == "FALHA"


def test_c08_apanha_ficheiro_com_epoca_trocada():
    # Jogo de agosto de 2022 num ficheiro chamado 2021-22
    jogos = pd.DataFrame([jogo(Data=pd.Timestamp("2022-08-10"))])
    assert estado_do_ultimo(controlos.controlo_datas, jogos) == "FALHA"


def test_c08_aceita_fim_de_epoca_em_julho():
    # A época 2019-20 acabou em julho de 2020 (COVID): não pode dar falha
    jogos = pd.DataFrame([jogo(Epoca="19-20", Data=pd.Timestamp("2020-07-26"))])
    assert estado_do_ultimo(controlos.controlo_datas, jogos) == "OK"


def test_c11_apanha_odd_abaixo_de_1():
    jogos = pd.DataFrame([jogo(OddCasaB365=0.95)])
    assert estado_do_ultimo(controlos.controlo_odds_plausiveis, jogos) == "FALHA"


def test_c11_apanha_odd_mal_escrita():
    # 21.0 em vez de 2.10: a margem da casa fica muito abaixo de 1
    jogos = pd.DataFrame([jogo(OddCasaB365=21.0)])
    assert estado_do_ultimo(controlos.controlo_odds_plausiveis, jogos) == "FALHA"


def test_c11_ignora_jogos_sem_odds():
    # Odds em falta são tratadas no C09, não aqui
    jogos = pd.DataFrame([jogo(OddCasaB365=None, OddEmpateB365=None, OddForaB365=None)])
    assert estado_do_ultimo(controlos.controlo_odds_plausiveis, jogos) == "OK"