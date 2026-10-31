"""
=====================================================================
 TESTES DO GRADIENT BOOSTING
=====================================================================
 Usam uma liga inventada com uma só variável, "Forca": quanto maior,
 mais a equipa da casa ganha. Assim sabe-se o que o modelo deve dar.
=====================================================================
"""
import numpy as np
import pandas as pd
import pytest

import configuracao as cfg
import func.avaliacao as av
import func.boosting as gb

GRELHA_PEQUENA = {"learning_rate": [0.1], "max_depth": [1, 2], "max_iter": [20], "min_samples_leaf": [20]}


def liga_inventada(epocas=4, jogos_por_epoca=300, semente=0):
    gerador = np.random.default_rng(semente)
    forca = gerador.normal(size=epocas * jogos_por_epoca)
    # Força alta -> casa ganha; força baixa -> fora ganha; perto de 0 -> mais empates
    sorteio = forca + gerador.normal(scale=0.8, size=len(forca))
    resultado = np.where(sorteio > 0.4, "H", np.where(sorteio < -0.4, "A", "D"))
    return pd.DataFrame({"Epoca": np.repeat(cfg.EPOCAS_ESPERADAS[:epocas], jogos_por_epoca),
                         "Forca": forca, "Resultado": resultado})


def test_probabilidades_na_ordem_casa_empate_fora():
    dados = liga_inventada()
    treino, teste = dados[dados["Epoca"] < cfg.EPOCAS_ESPERADAS[3]], pd.DataFrame(
        {"Epoca": cfg.EPOCAS_ESPERADAS[3], "Forca": [-2.0, 2.0]})
    p = gb.criar_previsor(["Forca"], GRELHA_PEQUENA)(treino, teste)
    assert p.sum(axis=1) == pytest.approx([1, 1])
    assert p[1, 0] > p[0, 0]          # força alta: mais vitória da casa (1.ª coluna)
    assert p[0, 2] > p[1, 2]          # força baixa: mais vitória de fora (3.ª coluna)


def test_resultado_da_epoca_a_prever_nao_e_usado():
    # Sem fuga: baralhar os resultados do teste não pode mudar nada
    dados = liga_inventada()
    treino, teste = dados[dados["Epoca"] < cfg.EPOCAS_ESPERADAS[3]], dados[dados["Epoca"] == cfg.EPOCAS_ESPERADAS[3]]
    baralhado = teste.assign(Resultado=teste["Resultado"].sample(frac=1, random_state=1).to_numpy())
    original = gb.criar_previsor(["Forca"], GRELHA_PEQUENA)(treino, teste)
    novo = gb.criar_previsor(["Forca"], GRELHA_PEQUENA)(treino, baralhado)
    assert novo == pytest.approx(original)


def test_afinacao_preve_as_ultimas_epocas_do_treino():
    # Treino com 4 épocas e GB_EPOCAS_AFINACAO = 2: o erro tem de ser a média do
    # log loss da 3.ª época (treinada com 1.ª e 2.ª) e da 4.ª (treinada com 1.ª a 3.ª).
    # Confirma também o atalho: o erro com 10 árvores, lido "pelo caminho" do modelo
    # de 20 árvores, tem de ser igual ao de um modelo treinado só com 10 árvores.
    dados = liga_inventada(epocas=4)
    p = {"learning_rate": 0.1, "max_depth": 1, "min_samples_leaf": 20}
    erros = gb.erros_por_arvores(dados, ["Forca"], p, [10, 20])
    for n in [10, 20]:
        esperado = []
        for epoca in cfg.EPOCAS_ESPERADAS[4 - cfg.GB_EPOCAS_AFINACAO:4]:
            antes, durante = dados[dados["Epoca"] < epoca], dados[dados["Epoca"] == epoca]
            modelo = gb.criar_modelo({**p, "max_iter": n}).fit(antes[["Forca"]], antes["Resultado"])
            esperado.append(av.medidas_por_jogo(av.prever(modelo, durante[["Forca"]]), durante["Resultado"])["LogLoss"].mean())
        assert erros[n] == pytest.approx(np.mean(esperado))
        assert erros[n] < np.log(3)      # melhor do que dizer 1/3 a tudo


def test_parametros_escolhidos_ficam_guardados():
    dados = liga_inventada()
    treino, teste = dados[dados["Epoca"] < cfg.EPOCAS_ESPERADAS[3]], dados[dados["Epoca"] == cfg.EPOCAS_ESPERADAS[3]]
    previsor = gb.criar_previsor(["Forca"], GRELHA_PEQUENA)
    previsor(treino, teste)
    escolhido = previsor.escolhidos[cfg.EPOCAS_ESPERADAS[3]]
    assert escolhido["max_depth"] in GRELHA_PEQUENA["max_depth"]