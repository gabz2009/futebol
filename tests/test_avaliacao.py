"""
=====================================================================
 TESTES DAS MEDIDAS E DA VALIDAÇÃO WALK-FORWARD
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest

import configuracao as cfg
import func.avaliacao as av


def test_medidas_de_um_jogo_calculadas_a_mao():
    # Previsão 50% casa, 30% empate, 20% fora, e ganhou a casa
    m = av.medidas_por_jogo([[0.5, 0.3, 0.2]], ["H"]).iloc[0]
    assert m["Acerto"] == 1
    assert m["LogLoss"] == pytest.approx(-np.log(0.5))                  # 0,693
    assert m["Brier"] == pytest.approx(0.5**2 + 0.3**2 + 0.2**2)        # 0,38
    # RPS: acumuladas previstas (0,5; 0,8) contra reais (1; 1)
    assert m["RPS"] == pytest.approx(((0.5 - 1) ** 2 + (0.8 - 1) ** 2) / 2)   # 0,145


def test_rps_castiga_menos_o_erro_vizinho():
    # Previsão 80% casa. Acabar empatado (vizinho) tem de custar menos do que ganhar fora
    empate = av.medidas_por_jogo([[0.8, 0.1, 0.1]], ["D"]).iloc[0]["RPS"]
    fora = av.medidas_por_jogo([[0.8, 0.1, 0.1]], ["A"]).iloc[0]["RPS"]
    assert empate < fora


def test_walk_forward_so_treina_com_epocas_anteriores():
    e = cfg.EPOCAS_ESPERADAS
    variaveis = pd.DataFrame({
        "JogoID": [f"j{i}" for i in range(5)],
        "Epoca": [e[0], e[1], e[2], e[3], e[4]],
        "Uso": ["Aquecimento", "Treino", "Treino", "Validação", "Validação"],
        "Resultado": ["H", "D", "A", "H", "A"],
    })
    vistos = {}

    def previsor(treino, teste):
        # Regista que épocas foram usadas no treino de cada época de validação
        vistos[teste["Epoca"].iloc[0]] = sorted(treino["Epoca"].unique())
        return np.full((len(teste), 3), 1 / 3)

    av.walk_forward(variaveis, previsor)
    # Valida e[3] com e[1] e e[2] (sem o aquecimento); valida e[4] também com e[3]
    assert vistos[e[3]] == [e[1], e[2]]
    assert vistos[e[4]] == [e[1], e[2], e[3]]

def test_calibracao_perfeita_da_ece_zero():
    # 10 jogos, sempre 50% / 30% / 20%, e aconteceu exatamente 5 H, 3 D e 2 A
    resultados = pd.DataFrame({
        "Resultado": ["H"] * 5 + ["D"] * 3 + ["A"] * 2,
        "ProbH": 0.5, "ProbD": 0.3, "ProbA": 0.2,
    })
    ece = av.ece_por_resultado(resultados)
    assert ece["Média"] == pytest.approx(0)


def test_calibracao_com_confianca_a_mais_da_ece_positiva():
    # Diz sempre 90% casa, mas a casa só ganha metade das vezes
    resultados = pd.DataFrame({
        "Resultado": ["H", "A"] * 5,
        "ProbH": 0.9, "ProbD": 0.05, "ProbA": 0.05,
    })
    assert av.ece_por_resultado(resultados)["H"] == pytest.approx(0.4)



def tabela_modelo(probabilidades, ids=("j1", "j2")):
    """Tabela no formato do walk_forward, só com o que a combinação usa."""
    p = np.array(probabilidades)
    return pd.DataFrame({"JogoID": list(ids), "Epoca": "x", "Resultado": ["H", "A"],
                         "ProbH": p[:, 0], "ProbD": p[:, 1], "ProbA": p[:, 2]})


def test_media_geometrica_exemplo_feito_a_mao():
    # GAP 80/15/5 e Dixon-Coles 40/30/30. Raízes: 0,566 / 0,212 / 0,122 (somam 0,900)
    # Depois de voltar a somar 1: 62,8% / 23,6% / 13,6%
    a = tabela_modelo([[0.80, 0.15, 0.05], [0.5, 0.3, 0.2]])
    b = tabela_modelo([[0.40, 0.30, 0.30], [0.5, 0.3, 0.2]])
    c = av.media_geometrica([a, b])
    assert c.loc[0, ["ProbH", "ProbD", "ProbA"]].to_numpy(dtype=float) == pytest.approx([0.628, 0.236, 0.136], abs=0.001)
    # Se os dois modelos dizem o mesmo, a combinação diz o mesmo
    assert c.loc[1, ["ProbH", "ProbD", "ProbA"]].to_numpy(dtype=float) == pytest.approx([0.5, 0.3, 0.2])
    # As medidas são recalculadas: o 1.º jogo acabou H, log loss = -log(0,628)
    assert c.loc[0, "LogLoss"] == pytest.approx(-np.log(0.628), abs=0.002)


def test_media_geometrica_recusa_jogos_trocados():
    a = tabela_modelo([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]], ids=("j1", "j2"))
    b = tabela_modelo([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]], ids=("j2", "j1"))
    with pytest.raises(ValueError):
        av.media_geometrica([a, b])


def test_walk_forward_do_teste_treina_com_todas_as_epocas_anteriores():
    # Treino e validação entram no treino do teste; o aquecimento e a própria época não
    variaveis = pd.DataFrame({
        "JogoID": ["a", "t", "v", "x"], "Resultado": ["H", "D", "A", "H"],
        "Epoca": [cfg.EPOCAS_ESPERADAS[i] for i in range(4)],
        "Uso": ["Aquecimento", "Treino", "Validação", "Teste"]})
    vistos = {}

    def previsor(treino, teste):
        vistos["treino"], vistos["teste"] = list(treino["JogoID"]), list(teste["JogoID"])
        return np.full((len(teste), 3), 1 / 3)

    av.walk_forward(variaveis, previsor, uso="Teste")
    assert vistos == {"treino": ["t", "v"], "teste": ["x"]}