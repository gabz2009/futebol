"""
=====================================================================
 TESTES DAS VARIÁVEIS (FASE 2)
=====================================================================
 Usam uma mini-liga inventada, com poucos jogos, para se conseguir
 confirmar as contas à mão.
=====================================================================
"""
import pandas as pd
import pytest

import configuracao as cfg
import func.elo as elo
import func.variaveis as variaveis_mod
import func.pi_ratings as pi_ratings

EPOCA = cfg.EPOCAS_ESPERADAS[0]       # primeira época dos dados, no formato da configuração


def mini_liga():
    """A joga 3 vezes em casa contra B, C e D e marca 1, 2 e 3 golos."""
    jogos = pd.DataFrame({
        "JogoID": ["j1", "j2", "j3"],
        "Epoca": EPOCA,
        "Data": pd.to_datetime(["2017-08-06", "2017-08-13", "2017-08-20"]),
        "Hora": None,
        "EquipaCasa": ["A", "A", "A"],
        "EquipaFora": ["B", "C", "D"],
        "GolosCasa": [1, 2, 3], "GolosFora": [0, 2, 4],
        "Resultado": ["H", "D", "A"],
        "RematesBalizaCasa": [3, 4, 5], "RematesBalizaFora": [1, 2, 6],
        "OddCasaB365": 2.0, "OddEmpateB365": 3.4, "OddForaB365": 3.8,
        "OddCasaMedia": 2.0, "OddEmpateMedia": 3.4, "OddForaMedia": 3.8,
        "EpocaCOVID": False,
    })
    epocas = pd.DataFrame({"Epoca": [EPOCA], "Uso": ["Aquecimento"]})
    return jogos, epocas


def test_media_usa_so_os_jogos_anteriores():
    jogos, epocas = mini_liga()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos), epocas).set_index("JogoID")
    coluna = f"CasaGolosMarcadosUlt{cfg.JANELA_FORMA}"
    assert pd.isna(v.loc["j1", coluna])          # 1.º jogo: ainda não há jogos anteriores
    assert v.loc["j2", coluna] == 1              # só o j1
    assert v.loc["j3", coluna] == 1.5            # média de j1 e j2, nunca o próprio j3


def test_pontos_contam_vitoria_empate_derrota():
    jogos, epocas = mini_liga()
    v = variaveis_mod.criar_variaveis(jogos, elo.calcular_elo(jogos), pi_ratings.calcular_pi_ratings(jogos), epocas).set_index("JogoID")
    # Antes do j3, A tinha uma vitória (3) e um empate (1): média 2
    assert v.loc["j3", f"CasaPontosUlt{cfg.JANELA_FORMA}"] == 2


def test_elo_antes_do_jogo_e_atualizacao():
    jogos, _ = mini_liga()
    resultado = elo.calcular_elo(jogos).set_index("JogoID")
    # Primeiro jogo: as duas equipas começam com o Elo inicial
    assert resultado.loc["j1", "EloCasa"] == cfg.ELO_INICIAL
    # A ganhou o j1: o Elo dela no j2 sobe exatamente K x (1 - esperado)
    esperado = elo.probabilidade_esperada(cfg.ELO_INICIAL, cfg.ELO_INICIAL)
    assert resultado.loc["j2", "EloCasa"] == pytest.approx(cfg.ELO_INICIAL + cfg.ELO_K * (1 - esperado))


def test_probabilidades_das_odds_somam_1():
    jogos, _ = mini_liga()
    prob = variaveis_mod.probabilidades_odds(jogos)
    soma = prob[["ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]].sum(axis=1)
    assert soma.round(9).eq(1).all()

def test_pi_ratings_exemplo_de_dois_jogos():
    """O exemplo explicado à mão: A 2-0 B e depois B 1-1 A."""
    jogos = pd.DataFrame({
        "JogoID": ["j1", "j2"], "Epoca": EPOCA,
        "Data": pd.to_datetime(["2017-08-06", "2017-08-13"]), "Hora": None,
        "EquipaCasa": ["A", "B"], "EquipaFora": ["B", "A"],
        "GolosCasa": [2, 1], "GolosFora": [0, 1],
    })
    pi = pi_ratings.calcular_pi_ratings(jogos).set_index("JogoID")
    # Antes do 1.º jogo, todos a 0
    assert pi.loc["j1", "PiCasa"] == 0 and pi.loc["j1", "PiFora"] == 0
    # Antes do 2.º jogo: B em casa desceu 70% de 0,050 e A fora subiu o mesmo
    assert pi.loc["j2", "PiCasa"] == pytest.approx(-0.0351, abs=1e-4)
    assert pi.loc["j2", "PiFora"] == pytest.approx(0.0351, abs=1e-4)
    # A diferença esperada no 2.º jogo favorece ligeiramente A (fora)
    assert pi.loc["j2", "PiDifEsperada"] == pytest.approx(-0.0546, abs=1e-4)