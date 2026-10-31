"""
=====================================================================
 TESTES DO CALENDÁRIO (API do football-data.org)
=====================================================================
 Usam uma resposta da API inventada, com o mesmo formato da real,
 para não depender da internet nem da chave.
=====================================================================
"""
import json

import pandas as pd
import pytest

import configuracao as cfg
import func.calendario as calendario_mod
import func.controlos as controlos

# Dois nomes da API e a sua tradução (tirados de cfg.NOMES_API)
NOME_API = {nosso: api for api, nosso in cfg.NOMES_API.items()}


def resposta_api(jogos):
    """jogos = lista de (data e hora UTC, casa, fora, estado, golos casa, golos fora), com os nossos nomes."""
    return {"matches": [
        {"id": 100 + i, "utcDate": quando, "status": estado, "matchday": 1,
         "homeTeam": {"name": NOME_API[casa]}, "awayTeam": {"name": NOME_API[fora]},
         "score": {"fullTime": {"home": gc, "away": gf}}}
        for i, (quando, casa, fora, estado, gc, gf) in enumerate(jogos)],
        "descarregado_em": "2026-10-31T12:00:00"}


def ler(tmp_path, jogos):
    caminho = tmp_path / "calendario.json"
    caminho.write_text(json.dumps(resposta_api(jogos)), encoding="utf-8")
    return calendario_mod.ler_calendario(caminho)


def jogos_csv(*linhas):
    """Jogos já jogados, como na tabela jogos (do football-data.co.uk)."""
    return pd.DataFrame([{"JogoID": f"{cfg.EPOCA_ATUAL}_{c}_{f}", "Epoca": cfg.EPOCA_ATUAL,
                          "GolosCasa": gc, "GolosFora": gf} for c, f, gc, gf in linhas],
                        columns=["JogoID", "Epoca", "GolosCasa", "GolosFora"])


def test_nomes_traduzidos_hora_de_lisboa_e_jogoid(tmp_path):
    # 19:15 UTC em agosto = 20:15 em Lisboa (hora de verão)
    origem, descarregado = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "TIMED", None, None)])
    calendario = calendario_mod.criar_calendario(origem)
    jogo = calendario.iloc[0]
    assert (jogo["EquipaCasa"], jogo["EquipaFora"]) == ("Benfica", "Porto")
    assert (jogo["Data"], jogo["Hora"]) == ("2026-08-07", "20:15")
    assert jogo["JogoID"] == f"{cfg.EPOCA_ATUAL}_Benfica_Porto"
    assert descarregado == "2026-10-31T12:00:00"


def test_hora_de_inverno(tmp_path):
    # 20:00 UTC em dezembro = 20:00 em Lisboa (sem hora de verão)
    origem, _ = ler(tmp_path, [("2026-12-20T20:00:00Z", "Benfica", "Porto", "TIMED", None, None)])
    assert calendario_mod.criar_calendario(origem).iloc[0]["Hora"] == "20:00"


def test_nome_sem_traducao_da_falha(tmp_path):
    origem, _ = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "TIMED", None, None)])
    origem.loc[0, "EquipaCasaAPI"] = "Clube Inventado FC"
    controlos.iniciar()
    controlos.controlo_nomes_calendario(origem)
    assert controlos.controlos[-1]["Estado"] == "FALHA"
    assert "Clube Inventado FC" in controlos.controlos[-1]["Detalhe"]


def estados(calendario, origem, jogos):
    controlos.iniciar()
    controlos.controlo_calendario_e_jogos(calendario, origem, jogos)
    return {c["Controlo"]: c["Estado"] for c in controlos.controlos}


def test_as_duas_fontes_batem_certo(tmp_path):
    origem, _ = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "FINISHED", 2, 1),
                               ("2026-08-14T19:15:00Z", "Porto", "Benfica", "TIMED", None, None)])
    calendario = calendario_mod.criar_calendario(origem)
    assert estados(calendario, origem, jogos_csv(("Benfica", "Porto", 2, 1))) == {"C17": "OK", "C18": "OK", "C19": "OK"}


def test_golos_diferentes_nas_duas_fontes_da_falha(tmp_path):
    origem, _ = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "FINISHED", 2, 1)])
    calendario = calendario_mod.criar_calendario(origem)
    assert estados(calendario, origem, jogos_csv(("Benfica", "Porto", 1, 1)))["C18"] == "FALHA"


def test_jogo_jogado_que_nao_esta_no_calendario_da_falha(tmp_path):
    origem, _ = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "FINISHED", 2, 1)])
    calendario = calendario_mod.criar_calendario(origem)
    jogos = jogos_csv(("Benfica", "Porto", 2, 1), ("Sp Braga", "Porto", 0, 0))
    assert estados(calendario, origem, jogos)["C17"] == "FALHA"


def test_jogo_adiado_ou_ainda_sem_csv_e_so_aviso(tmp_path):
    origem, _ = ler(tmp_path, [("2026-08-07T19:15:00Z", "Benfica", "Porto", "FINISHED", 2, 1),
                               ("2026-08-14T19:15:00Z", "Porto", "Benfica", "POSTPONED", None, None)])
    calendario = calendario_mod.criar_calendario(origem)
    resultado = estados(calendario, origem, jogos_csv())        # o CSV ainda não tem nenhum jogo
    assert resultado == {"C17": "OK", "C18": "OK", "C19": "AVISO"}
    assert controlos.controlos[-1]["Critico"] is False