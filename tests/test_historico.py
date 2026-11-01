"""
=====================================================================
 TESTES DO HISTÓRICO DA SIMULAÇÃO
=====================================================================
"""
import sqlite3

import pandas as pd

import configuracao as cfg
import func.historico as historico


def calendario():
    return pd.DataFrame({
        "JogoID": ["a", "b", "c", "d", "e"], "Jornada": [1, 1, 2, 2, 3],
        "Data": ["2026-08-08", "2026-08-09", "2026-08-15", "2026-08-16", "2026-08-22"],
        "Estado": ["FINISHED", "FINISHED", "FINISHED", "POSTPONED", "TIMED"]})


def test_corte_de_cada_jornada():
    cortes = historico.cortes_por_jornada(calendario()).set_index("Jornada")["DataCorte"]
    assert cortes[0] == pd.Timestamp("2026-08-08")     # início da época = 1.º jogo da jornada 1
    assert cortes[1] == pd.Timestamp("2026-08-15")     # depois da jornada 1 = 1.º jogo da jornada 2
    assert cortes[3] == pd.Timestamp("2026-08-23")     # fotografia final: dia a seguir ao último jogo


def test_fotografia_so_fica_pronta_com_todos_os_jogos_antes_do_corte():
    jogos = pd.DataFrame({"JogoID": ["a", "b"]})
    assert historico.fotografia_pronta(pd.Timestamp("2026-08-15"), calendario(), jogos)       # a e b já no CSV
    assert not historico.fotografia_pronta(pd.Timestamp("2026-08-22"), calendario(), jogos)   # falta o c (o d está adiado)


def test_guardar_a_mesma_jornada_duas_vezes_substitui(tmp_path):
    caminho = tmp_path / "historico.db"
    fotografia = pd.DataFrame([{
        "Epoca": cfg.EPOCA_ATUAL, "Jornada": 1, "DataCorte": "2026-08-15", "Posicao": 1, "Equipa": "Benfica",
        "Jogos": 1, "Vitorias": 1, "Empates": 0, "Derrotas": 0, "GolosMarcados": 2, "GolosSofridos": 0,
        "Pontos": 3, "DiferencaGolos": 2, "PontosEsperados": 80.0, "PontosP10": 73.0, "PontosP90": 87.0,
        "PosicaoMedia": 1.8, "ProbCampeao": 0.4, "ProbTop3": 0.99, "ProbEuropa": 1.0,
        "ProbPlayoffDescida": 0.0, "ProbDescida": 0.0, "Simulacoes": 10000}])
    historico.guardar(fotografia, caminho, cfg.ESQUEMA_HISTORICO_SQL)
    historico.guardar(fotografia.assign(ProbCampeao=0.5), caminho, cfg.ESQUEMA_HISTORICO_SQL)
    assert historico.jornadas_guardadas(caminho) == {1}
    with sqlite3.connect(caminho) as ligacao:
        assert ligacao.execute("SELECT COUNT(*), MAX(ProbCampeao) FROM historico_simulacao").fetchone() == (1, 0.5)