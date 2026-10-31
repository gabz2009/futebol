"""
=====================================================================
 TESTES DO MODELO DIXON-COLES
=====================================================================
 1. Contas da tabela de resultados confirmadas à mão
 2. O modelo aprende (quem marca mais tem mais ataque)
 3. Sem fuga: alterar um jogo não muda a sua previsão, só as seguintes
 4. Uma equipa promovida sem jogos entra com os números de quem desceu
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest

import configuracao as cfg
import func.dixon_coles as dc

EPOCA_1, EPOCA_2 = cfg.EPOCAS_ESPERADAS[0], cfg.EPOCAS_ESPERADAS[1]


def mini_ligas():
    """Época 1: A, B, C e D jogam todos contra todos, 3 voltas (36 jogos).
    A marca sempre 3 golos, as outras 1. Na época 2, D desce e entra E."""
    linhas, data = [], pd.Timestamp("2017-08-06")
    for epoca, equipas, voltas in [(EPOCA_1, "ABCD", 3), (EPOCA_2, "ABCE", 1)]:
        for _ in range(voltas):
            for casa in equipas:
                for fora in equipas:
                    if casa != fora:
                        linhas.append({"JogoID": f"{epoca}_{casa}_{fora}_{len(linhas)}", "Epoca": epoca,
                                       "Data": data, "EquipaCasa": casa, "EquipaFora": fora,
                                       "GolosCasa": 3 if casa == "A" else 1,
                                       "GolosFora": 3 if fora == "A" else 1})
                        data += pd.Timedelta(days=7)
    return pd.DataFrame(linhas)


def test_tabela_com_rho_zero_e_o_poisson():
    # Golos esperados 1,5 e 1,0. Com rho = 0, o 0-0 é e^-1,5 x e^-1 = e^-2,5 = 0,0821
    tabela = dc.tabela_resultados(1.5, 1.0, rho=0)
    assert tabela.sum() == pytest.approx(1)
    assert tabela[0, 0] == pytest.approx(np.exp(-2.5), rel=1e-4)
    assert tabela[2, 1] == pytest.approx(np.exp(-2.5) * 1.5**2 / 2 * 1.0, rel=1e-4)    # 2-1


def test_rho_so_mexe_nos_resultados_baixos():
    # Com rho = 0,1: o 0-0 fica x (1 - 1,5 x 1,0 x 0,1) = x 0,85. O 2-1 não muda.
    # (As 4 correções anulam-se umas às outras, por isso o total continua a ser 1.)
    sem, com = dc.tabela_resultados(1.5, 1.0, rho=0), dc.tabela_resultados(1.5, 1.0, rho=0.1)
    assert com[0, 0] == pytest.approx(sem[0, 0] * 0.85, rel=1e-4)
    assert com[1, 1] == pytest.approx(sem[1, 1] * 0.90, rel=1e-4)
    assert com[2, 1] == pytest.approx(sem[2, 1], rel=1e-4)


def test_probabilidades_1x2_somam_a_tabela():
    # Linha = golos da casa. 1-0 (0,3) e 2-1 (0,1) são vitórias da casa.
    tabela = np.array([[0.2, 0.1, 0.0],
                       [0.3, 0.1, 0.1],
                       [0.0, 0.1, 0.1]])
    casa, empate, fora = dc.probabilidades_1x2(tabela)
    assert (casa, empate, fora) == pytest.approx((0.4, 0.4, 0.2))


def test_quem_marca_mais_tem_mais_ataque():
    jogos = mini_ligas()
    epoca_1 = jogos[jogos["Epoca"] == EPOCA_1]
    modelo = dc.ajustar(epoca_1, epoca_1["Data"].max() + pd.Timedelta(days=1))
    ataque = dict(zip(modelo["posicao"], modelo["ataque"]))
    assert ataque["A"] > max(ataque["B"], ataque["C"], ataque["D"])
    # Com uma penalização enorme, todos ficam quase na média (0)
    forte = dc.ajustar(epoca_1, epoca_1["Data"].max() + pd.Timedelta(days=1), ridge=1e6)
    assert np.abs(forte["ataque"]).max() < 0.01


def test_sem_fuga_de_informacao():
    jogos = mini_ligas()
    teste = jogos[jogos["Epoca"] == EPOCA_2]
    alvo = teste.iloc[3]
    seguinte = teste[(teste["Data"] > alvo["Data"]) & (teste["EquipaCasa"] == alvo["EquipaCasa"])].iloc[0]

    originais = dc.criar_previsor(jogos)(None, teste)
    alterados = jogos.copy()
    alterados.loc[alterados["JogoID"] == alvo["JogoID"], ["GolosCasa", "GolosFora"]] = [0, 7]
    novos = dc.criar_previsor(alterados)(None, teste)

    linha = {j: i for i, j in enumerate(teste["JogoID"])}
    assert originais[linha[alvo["JogoID"]]] == pytest.approx(novos[linha[alvo["JogoID"]]])
    assert originais[linha[seguinte["JogoID"]]] != pytest.approx(novos[linha[seguinte["JogoID"]]])


def test_ordem_dos_jogos_nao_muda_a_previsao():
    # O previsor ordena por data sozinho e devolve pela ordem em que recebeu
    jogos = mini_ligas()
    teste = jogos[jogos["Epoca"] == EPOCA_2]
    previsor = dc.criar_previsor(jogos)
    normal = previsor(None, teste)
    invertida = previsor(None, teste.iloc[::-1])
    assert invertida[::-1] == pytest.approx(normal)


def test_promovida_entra_com_os_numeros_de_quem_desceu():
    # D desceu e E subiu: no 1.º jogo de E, E tem de valer o mesmo que D
    jogos = mini_ligas()
    teste = jogos[jogos["Epoca"] == EPOCA_2]
    primeiro_e = teste[(teste["EquipaCasa"] == "E") | (teste["EquipaFora"] == "E")].iloc[0]
    previsto = dc.criar_previsor(jogos)(None, teste.loc[[primeiro_e.name]])[0]

    modelo = dc.ajustar(jogos[jogos["Data"] < primeiro_e["Data"]], primeiro_e["Data"])
    i_casa = modelo["posicao"]["D" if primeiro_e["EquipaCasa"] == "E" else primeiro_e["EquipaCasa"]]
    i_fora = modelo["posicao"]["D" if primeiro_e["EquipaFora"] == "E" else primeiro_e["EquipaFora"]]
    casa = np.exp(modelo["base"] + modelo["vantagem"] + modelo["ataque"][i_casa] + modelo["defesa"][i_fora])
    fora = np.exp(modelo["base"] + modelo["ataque"][i_fora] + modelo["defesa"][i_casa])
    esperado = dc.probabilidades_1x2(dc.tabela_resultados(casa, fora, modelo["rho"]))
    assert previsto == pytest.approx(esperado)



def test_gradiente_certo():
    # O gradiente feito à mão tem de bater com o gradiente estimado numericamente
    # (mexer em cada número um bocadinho e ver quanto o custo muda)
    from scipy.optimize import check_grad
    jogos = mini_ligas()
    # Garante jogos 0-0, 0-1, 1-0 e 1-1, para testar também as contas do rho
    jogos.loc[:3, ["GolosCasa", "GolosFora"]] = [[0, 0], [0, 1], [1, 0], [1, 1]]
    custo_e_gradiente, _, _, numero = dc.criar_custo(jogos, jogos["Data"].max() + pd.Timedelta(days=1), xi=0.001, ridge=2)
    ponto = np.random.default_rng(0).normal(scale=0.1, size=numero)
    erro = check_grad(lambda t: custo_e_gradiente(t)[0], lambda t: custo_e_gradiente(t)[1], ponto)
    assert erro < 1e-3 * np.linalg.norm(custo_e_gradiente(ponto)[1])