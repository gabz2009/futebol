import func.espn as espn
import pandas as pd

def calendario(*jogos):
    return {"matches": [{"utcDate": f"{dia}T20:30:00Z", "status": estado} for dia, estado in jogos]}


def test_dias_por_descarregar(tmp_path):
    # Dia 07: 2 jogos terminados e 2 fichas gravadas -> completo. Dia 08: 2 terminados, só 1 ficha -> falta.
    # Dia 15: o jogo ainda não acabou -> não se pede
    (tmp_path / "2026-11-07_1.json").write_text("{}")
    (tmp_path / "2026-11-07_2.json").write_text("{}")
    (tmp_path / "2026-11-08_3.json").write_text("{}")
    jogos = calendario(("2026-11-07", "FINISHED"), ("2026-11-07", "FINISHED"), ("2026-11-08", "FINISHED"),
                       ("2026-11-08", "FINISHED"), ("2026-11-15", "TIMED"))
    assert espn.dias_por_descarregar(jogos, tmp_path) == ["2026-11-08"]


def ficha(acabado, jogadores_casa, jogadores_fora):
    return {"header": {"competitions": [{"status": {"type": {"completed": acabado}}}]},
            "rosters": [{"roster": [{}] * jogadores_casa}, {"roster": [{}] * jogadores_fora}]}


def test_so_se_grava_a_ficha_completa():
    assert espn.ficha_completa(ficha(True, 23, 23))
    assert not espn.ficha_completa(ficha(False, 23, 23))   # jogo ainda não acabado
    assert not espn.ficha_completa(ficha(True, 23, 0))     # falta a ficha de uma equipa


def jogador(jogador_id, nome, posicao, titular, entrou=False, saiu=False, **estatisticas):
    return {"athlete": {"id": jogador_id, "displayName": nome}, "position": {"name": posicao},
            "starter": titular, "subbedIn": entrou, "subbedOut": saiu,
            "stats": [{"name": chave, "value": valor} for chave, valor in estatisticas.items()]}


def evento(tipo, segundos, equipa=None, *jogadores, golo=False):
    return {"type": {"text": tipo}, "clock": {"value": segundos}, "scoringPlay": golo, "shootout": False,
            **({"team": {"id": equipa}} if equipa else {}),
            "participants": [{"athlete": {"id": j}} for j in jogadores]}


def ficha_exemplo():
    return {
        "header": {"competitions": [{"date": "2026-11-08T20:30Z", "status": {"type": {"completed": True}}, "competitors": [
            {"homeAway": "home", "score": "0", "team": {"id": "21610", "displayName": "Estrela"}},
            {"homeAway": "away", "score": "1", "team": {"id": "1929", "displayName": "Benfica"}}]}]},
        "keyEvents": [evento("Kickoff", 0), evento("Goal", 1517, "1929", "339191", "361355", golo=True),
                      evento("Yellow Card", 2000, "21610", "303631"),
                      evento("Substitution", 3858, "1929", "332081", "329691"), evento("End Regular Time", 5700)],
        "rosters": [
            {"team": {"id": "21610"}, "roster": [jogador("303631", "Bernardo Schappo", "Center Left Defender", True,
                                                         yellowCards=1.0)]},
            {"team": {"id": "1929"}, "roster": [
                jogador("329691", "Tomás Araújo", "Center Right Defender", True, saiu=True),
                jogador("332081", "Alessandro Circati", "Center Right Defender", False, entrou=True),
                jogador("339191", "Gianluca Prestianni", "Right Winger", True, totalGoals=1.0, totalShots=3.0),
                jogador("999", "Suplente", "Substitute", False)]}],
        "boxscore": {"teams": [
            {"team": {"id": "21610"}, "statistics": [{"name": "possessionPct", "displayValue": "37.7"},
                                                     {"name": "totalPasses", "displayValue": "339"}]},
            {"team": {"id": "1929"}, "statistics": [{"name": "possessionPct", "displayValue": "62.3"},
                                                    {"name": "totalPasses", "displayValue": "561"}]}]}}


def test_jogo_e_eventos_da_ficha():
    ficha = ficha_exemplo()
    jogo = espn.jogo_da_ficha(ficha, "401885401")
    assert (jogo["NomeCasaESPN"], jogo["GolosCasa"], jogo["GolosFora"], jogo["Duracao"]) == ("Estrela", 0, 1, 95.0)
    eventos = espn.eventos_da_ficha(ficha, "401885401")
    # O início e o fim do jogo não interessam: ficam o golo, o cartão e a substituição
    assert list(eventos["Tipo"]) == ["Goal", "Yellow Card", "Substitution"]
    golo = eventos.iloc[0]
    assert (golo["Golo"], golo["Jogador1"], golo["Jogador2"]) == (True, "339191", "361355")


def test_minutos_e_golos_em_campo():
    ficha = ficha_exemplo()
    eventos = espn.eventos_da_ficha(ficha, "1")
    jogadores = espn.jogadores_da_ficha(ficha, "1", eventos, 95.0).set_index("JogadorID")
    # Tomás Araújo: titular, sai aos 64,3' (3858 s). Estava em campo no golo do Benfica (25,3')
    assert (jogadores.loc["329691", "Entrou"], round(jogadores.loc["329691", "Saiu"], 1)) == (0.0, 64.3)
    assert (jogadores.loc["329691", "GolosProEmCampo"], jogadores.loc["329691", "GolosContraEmCampo"]) == (1, 0)
    # Circati entra aos 64,3' e joga até ao fim (95'): já não apanhou o golo
    assert round(jogadores.loc["332081", "Minutos"], 1) == 30.7 and jogadores.loc["332081", "GolosProEmCampo"] == 0
    # O suplente que não entrou fica com 0 minutos; o defesa do Estrela sofreu o golo em campo
    assert jogadores.loc["999", "Minutos"] == 0 and pd.isna(jogadores.loc["999", "Linha"])
    assert jogadores.loc["303631", "GolosContraEmCampo"] == 1 and jogadores.loc["303631", "Amarelos"] == 1
    assert jogadores.loc["339191", "Linha"] == "AV" and jogadores.loc["339191", "Golos"] == 1


def test_posse_da_equipa():
    equipas = espn.estatisticas_equipa_da_ficha(ficha_exemplo(), "1").set_index("EquipaESPN")
    assert equipas.loc["1929", "PosseBola"] == 62.3 and equipas.loc["21610", "Passes"] == 339


def test_ligar_equipas_e_controlo_dos_golos():
    jogos = pd.DataFrame([espn.jogo_da_ficha(ficha_exemplo(), "1")])
    calendario = pd.DataFrame({"JogoID": ["x"], "Data": ["2026-11-08"], "EquipaCasa": ["Estrela"],
                               "EquipaFora": ["Benfica"], "GolosCasa": [0], "GolosFora": [1]})
    mapa = espn.mapear_equipas(jogos, calendario).set_index("EquipaESPN")
    assert mapa.loc["1929", "Equipa"] == "Benfica" and mapa.loc["21610", "Equipa"] == "Estrela"
    eventos = espn.eventos_da_ficha(ficha_exemplo(), "1")
    assert espn.golos_que_nao_batem(jogos, eventos).empty
    # Se o golo estivesse contado na equipa errada, o jogo aparecia no controlo
    eventos.loc[eventos["Golo"], "EquipaESPN"] = "21610"
    assert len(espn.golos_que_nao_batem(jogos, eventos)) == 1