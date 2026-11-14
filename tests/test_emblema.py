"""
=====================================================================
 TESTES DOS EMBLEMAS
=====================================================================
"""
import pandas as pd

import configuracao as cfg
import func.emblemas as emblemas


def equipa(nome, liga="Portuguese Primeira Liga", pais="Portugal", desporto="Soccer", genero="Male"):
    return {"strTeam": nome, "strLeague": liga, "strCountry": pais, "strSport": desporto,
            "strGender": genero, "strBadge": f"https://emblemas/{nome}.png"}


def test_escolhe_a_equipa_portuguesa_masculina_da_primeira_liga():
    candidatas = [equipa("Porto", pais="Brazil"), equipa("FC Porto"), equipa("FC Porto B", liga="Portuguese LigaPro"),
                  equipa("FC Porto Women", genero="Female")]
    assert emblemas.escolher_equipa(candidatas, "Porto")["strTeam"] == "FC Porto"


def test_sem_liga_decide_pelo_nome_igual_e_sem_acentos():
    candidatas = [equipa("Famalicão", liga="Portuguese Liga 3"), equipa("Famalicão B", liga="Portuguese Liga 3")]
    assert emblemas.escolher_equipa(candidatas, "Famalicao")["strTeam"] == "Famalicão"


def test_quando_nao_da_para_decidir_nao_escolhe():
    candidatas = [equipa("Belenenses", liga="Portuguese Liga 3"), equipa("Belenenses SAD", liga="Portuguese Liga 3")]
    assert emblemas.escolher_equipa(candidatas, "Belenenses B") is None
    assert emblemas.escolher_equipa(None, "Aves") is None                # a pesquisa não devolveu nada


def test_prioridade_manual_thesportsdb_football_data(monkeypatch):
    monkeypatch.setattr(cfg, "EMBLEMAS_MANUAIS", {"Benfica": "manual.png"})
    equipas = pd.DataFrame({"Equipa": ["Benfica", "Porto", "Arouca", "Aves"]})
    resultado = emblemas.juntar_emblemas(equipas, {"Benfica": "tsdb_b.png", "Porto": "tsdb_p.png"},
                                         {"Porto": "fd_p.png", "Arouca": "fd_a.png"}).set_index("Equipa")
    assert resultado.loc["Benfica", "EmblemaFonte"] == "Manual"
    assert resultado.loc["Porto", ["EmblemaURL", "EmblemaFonte"]].tolist() == ["tsdb_p.png", "TheSportsDB"]
    assert resultado.loc["Arouca", "EmblemaFonte"] == "football-data.org"
    assert pd.isna(resultado.loc["Aves", "EmblemaURL"])


def test_emblemas_da_api_com_os_nossos_nomes():
    api = {nosso: nome for nome, nosso in cfg.NOMES_API.items()}
    origem = pd.DataFrame({"EquipaCasaAPI": [api["Benfica"]], "EquipaForaAPI": [api["Porto"]],
                           "EmblemaCasaAPI": ["b.png"], "EmblemaForaAPI": ["p.png"]})
    assert emblemas.emblemas_football_data(origem) == {"Benfica": "b.png", "Porto": "p.png"}