"""
Funções para as fichas dos jogos da ESPN (API não oficial).
Os pedidos à internet ficam no script descarregar_jogadores.py; aqui só se decide e transforma,
para dar para testar sem internet.
"""
from collections import Counter
import pandas as pd
import configuracao as cfg


def dias_por_descarregar(calendario, pasta):
    """Os dias com jogos terminados (segundo o calendário da API) que ainda não têm todas as
    fichas gravadas. Os ficheiros chamam-se "AAAA-MM-DD_<id do jogo na ESPN>.json", por isso
    basta contá-los por dia."""
    terminados = Counter(jogo["utcDate"][:10] for jogo in calendario["matches"] if jogo["status"] == "FINISHED")
    gravados = Counter(ficheiro.name.split("_")[0] for ficheiro in pasta.glob("*.json"))
    return sorted(dia for dia, jogos in terminados.items() if gravados[dia] < jogos)


def ficha_completa(resumo):
    """Só se grava a ficha de um jogo acabado e com os jogadores das duas equipas. Logo a seguir
    ao jogo a ESPN às vezes ainda não a tem completa: fica para a próxima vez que se correr."""
    estado = resumo["header"]["competitions"][0]["status"]["type"]
    fichas = resumo.get("rosters", [])
    return bool(estado.get("completed")) and len(fichas) == 2 and all(equipa.get("roster") for equipa in fichas)


def jogo_da_ficha(ficha, evento_id):
    """As equipas, o resultado e a duração do jogo (em minutos, com os descontos da 2.ª parte)."""
    competicao = ficha["header"]["competitions"][0]
    lados = {lado["homeAway"]: lado for lado in competicao["competitors"]}
    fim = [e["clock"]["value"] for e in ficha.get("keyEvents", []) if e["type"]["text"] == "End Regular Time"]
    return {"EventoID": evento_id, "DataUTC": competicao["date"][:10],
            "EquipaCasaESPN": lados["home"]["team"]["id"], "NomeCasaESPN": lados["home"]["team"]["displayName"],
            "EquipaForaESPN": lados["away"]["team"]["id"], "NomeForaESPN": lados["away"]["team"]["displayName"],
            "GolosCasa": int(lados["home"]["score"]), "GolosFora": int(lados["away"]["score"]),
            "Duracao": fim[0] / 60 if fim else 90.0}


def eventos_da_ficha(ficha, evento_id):
    """Os golos, as substituições e os cartões. Nas substituições, o Jogador1 entra e o Jogador2 sai;
    nos golos, o Jogador1 marca e o Jogador2 assiste. O minuto vem em segundos no clock."""
    linhas = []
    for evento in ficha.get("keyEvents", []):
        tipo = evento["type"]["text"]
        golo = evento.get("scoringPlay", False) and not evento.get("shootout", False)
        if not (golo or tipo == "Substitution" or "Card" in tipo):
            continue
        participantes = [p["athlete"]["id"] for p in evento.get("participants", [])] + [None, None]
        linhas.append({"EventoID": evento_id, "Minuto": evento["clock"]["value"] / 60, "Tipo": tipo, "Golo": golo,
                       "EquipaESPN": evento.get("team", {}).get("id"),
                       "Jogador1": participantes[0], "Jogador2": participantes[1]})
    return pd.DataFrame(linhas, columns=["EventoID", "Minuto", "Tipo", "Golo", "EquipaESPN", "Jogador1", "Jogador2"])


def linha_da_posicao(posicao):
    """ "Center Left Defender" -> "DEF". As posições sem palavra conhecida (ex.: "Substitute") ficam vazias."""
    for palavra, linha in cfg.LINHAS_ESPN.items():
        if palavra in posicao:
            return linha
    return None

def lugar_no_campo(formacao, posicao_curta):
    """(X, Y) do titular no campo, pela formação da equipa e pela posição (ex.: 4-3-3 e "LF").
    Uma combinação que não esteja no CAMPO_POR_FORMACAO devolve (None, None) e o script avisa."""
    return cfg.CAMPO_POR_FORMACAO.get(formacao, {}).get(posicao_curta, (None, None))

def jogadores_da_ficha(ficha, evento_id, eventos, duracao):
    """Um jogador da ficha por linha: quando entrou e saiu, os minutos, as estatísticas e os golos
    a favor e contra da equipa enquanto esteve em campo (é daqui que sai o impacto)."""
    golos = eventos[eventos["Golo"]]
    linhas = []
    for equipa in ficha["rosters"]:
        equipa_id = equipa["team"]["id"]
        formacao = equipa.get("formation")
        for jogador in equipa["roster"]:
            jogador_id = jogador["athlete"]["id"]
            entrou = 0.0 if jogador["starter"] else None
            substituiu = None
            if jogador["subbedIn"]:
                entrada = eventos[(eventos["Tipo"] == "Substitution") & (eventos["Jogador1"] == jogador_id)]
                entrou = entrada["Minuto"].min() if len(entrada) else None
                substituiu = entrada["Jogador2"].iloc[0] if len(entrada) else None
            saiu = None
            if entrou is not None:
                saidas = eventos[((eventos["Tipo"] == "Substitution") & (eventos["Jogador2"] == jogador_id))
                                 | (eventos["Tipo"].str.contains("Red") & (eventos["Jogador1"] == jogador_id))]
                saiu = saidas["Minuto"].min() if len(saidas) else duracao
            em_campo = golos[(golos["Minuto"] >= entrou) & (golos["Minuto"] < saiu)] if entrou is not None else golos.iloc[0:0]
            estatisticas = {e["name"]: e.get("value") for e in jogador.get("stats", [])}
            posicao = jogador.get("position", {}).get("name", "")
            posicao_curta = jogador.get("position", {}).get("abbreviation")
            campo_x, campo_y = lugar_no_campo(formacao, posicao_curta) if jogador["starter"] else (None, None)
            linhas.append({
                "EventoID": evento_id, "EquipaESPN": equipa_id, "JogadorID": jogador_id,
                "Nome": jogador["athlete"]["displayName"],
                "NomeCurto": jogador["athlete"].get("shortName", jogador["athlete"]["displayName"]),
                "Posicao": posicao, "Linha": linha_da_posicao(posicao),
                "Formacao": formacao, "PosicaoCurta": posicao_curta, "CampoX": campo_x, "CampoY": campo_y,
                "Substituiu": substituiu, "Titular": int(jogador["starter"]),
                "Entrou": round(entrou, 1) if entrou is not None else None,
                "Saiu": round(saiu, 1) if saiu is not None else None,
                "Minutos": round(saiu - entrou, 1) if entrou is not None else 0.0,
                "GolosProEmCampo": int((em_campo["EquipaESPN"] == equipa_id).sum()),
                "GolosContraEmCampo": int((em_campo["EquipaESPN"] != equipa_id).sum()),
                **{nome: estatisticas.get(chave) for chave, nome in cfg.ESTATISTICAS_JOGADOR_ESPN.items()}})
    return pd.DataFrame(linhas)


def estatisticas_equipa_da_ficha(ficha, evento_id):
    """A posse e os passes de cada equipa no jogo (o boxscore da ESPN)."""
    linhas = []
    for equipa in ficha.get("boxscore", {}).get("teams", []):
        valores = {e["name"]: e.get("displayValue") for e in equipa.get("statistics", [])}
        linhas.append({"EventoID": evento_id, "EquipaESPN": equipa["team"]["id"],
                       **{nome: pd.to_numeric(valores.get(chave), errors="coerce")
                          for chave, nome in cfg.ESTATISTICAS_EQUIPA_ESPN.items()}})
    return pd.DataFrame(linhas)


def mapear_equipas(jogos_espn, calendario):
    """Liga cada equipa da ESPN ao nome do nosso CSV pelos jogos: junta os dois lados pela data e
    pelo resultado e liga primeiro os pares que coincidem em mais jogos (um para um). Dois jogos
    no mesmo dia com o mesmo resultado criam pares errados, mas só uma ou duas vezes."""
    pares = jogos_espn.merge(calendario, left_on=["DataUTC", "GolosCasa", "GolosFora"],
                             right_on=["Data", "GolosCasa", "GolosFora"])
    colunas = ["EquipaESPN", "NomeESPN", "Equipa"]
    ligacoes = pd.concat([pares[["EquipaCasaESPN", "NomeCasaESPN", "EquipaCasa"]].set_axis(colunas, axis=1),
                          pares[["EquipaForaESPN", "NomeForaESPN", "EquipaFora"]].set_axis(colunas, axis=1)])
    contagem = ligacoes.groupby(colunas).size().reset_index(name="JogosIguais")
    escolhidos, usadas_espn, usadas_nossas = [], set(), set()
    for par in contagem.sort_values("JogosIguais", ascending=False).itertuples(index=False):
        if par.EquipaESPN not in usadas_espn and par.Equipa not in usadas_nossas:
            escolhidos.append(par)
            usadas_espn.add(par.EquipaESPN)
            usadas_nossas.add(par.Equipa)
    return pd.DataFrame(escolhidos, columns=contagem.columns).reset_index(drop=True)


def golos_que_nao_batem(jogos_espn, eventos):
    """Controlo: os golos contados nos eventos têm de dar o resultado final (apanha, por exemplo,
    um autogolo contado na equipa errada). Devolve os jogos que não batem."""
    golos = eventos[eventos["Golo"]].groupby(["EventoID", "EquipaESPN"]).size()
    casa = [golos.get((j.EventoID, j.EquipaCasaESPN), 0) for j in jogos_espn.itertuples()]
    fora = [golos.get((j.EventoID, j.EquipaForaESPN), 0) for j in jogos_espn.itertuples()]
    errados = (jogos_espn["GolosCasa"] != casa) | (jogos_espn["GolosFora"] != fora)
    return jogos_espn.loc[errados, ["EventoID", "NomeCasaESPN", "NomeForaESPN", "GolosCasa", "GolosFora"]]