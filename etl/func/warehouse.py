"""
=====================================================================
 DATA WAREHOUSE (PostgreSQL) PARA O POWER BI
=====================================================================
 O QUE FAZ
   Pega nas tabelas prontas do SQLite (futebol.db e historico.db) e
   transforma-as num esquema em estrela, a camada "gold":
     dimensões: dim_equipa, dim_jornada, dim_jogo
     factos:    fato_previsoes, fato_avaliacao_oficial, fato_simulacao,
                fato_posicoes, fato_classificacao_jornada, fato_historico

 PORQUÊ UM ESQUEMA EM ESTRELA
   Cada coisa fica num só sítio. Por exemplo, o resultado de um jogo
   está só na dim_jogo; as previsões de hoje e as previsões oficiais
   ligam-se a ela pelo JogoID. O Power BI foi feito para este formato:
   os filtros passam das dimensões para os factos.

 PORQUÊ ARREDONDAR
   O Power BI comprime cada coluna guardando os valores diferentes que
   ela tem. 0.41263817 e 0.41263822 contam como dois valores; com 4
   casas decimais passam a ser um só (0.4126). O modelo fica mais leve
   e no relatório não se nota diferença.
=====================================================================
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

import configuracao as cfg
import func.simulacao as simulacao

COLUNAS_SIMULACAO = ["PontosEsperados", "PontosP10", "PontosP90", "PosicaoMedia", "ProbCampeao", "ProbTop3",
                     "ProbEuropa", "ProbPlayoffDescida", "ProbDescida"]
COLUNAS_CLASSIFICACAO = ["Posicao", "Jogos", "Vitorias", "Empates", "Derrotas", "GolosMarcados", "GolosSofridos",
                         "DiferencaGolos", "Pontos"]


# ---------------------------------------------------------------------
# LIGAÇÃO
# ---------------------------------------------------------------------

def ler_env(caminho=cfg.FICHEIRO_CHAVE):
    """O ficheiro .env (linhas NOME=valor) como dicionário."""
    valores = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        nome, sinal, valor = linha.partition("=")
        if sinal and not nome.strip().startswith("#"):
            valores[nome.strip()] = valor.strip()
    return valores


def criar_motor(env):
    """Ligação ao PostgreSQL com os dados do .env. O URL.create trata dos caracteres
    especiais da palavra-passe (um @ ou um / partiam um endereço escrito à mão)."""
    endereco = URL.create("postgresql+psycopg", username=env["PG_UTILIZADOR"], password=env["PG_PALAVRA_PASSE"],
                          host=env["PG_HOST"], port=int(env["PG_PORTA"]), database=env["PG_BASE"])
    return create_engine(endereco)


# ---------------------------------------------------------------------
# TRANSFORMAÇÃO: do SQLite para o esquema em estrela
# ---------------------------------------------------------------------

def arredondar(tabela, casas=cfg.CASAS_DECIMAIS):
    """Probabilidades e medidas com 4 casas decimais; os pontos esperados e a posição média com 2."""
    tabela = tabela.copy()
    for coluna in tabela.columns:
        # to_numeric: uma coluna só com vazios vem do SQLite como texto (None), e aí o round dava erro.
        # Acontece, por exemplo, nas odds das previsões oficiais enquanto nenhum desses jogos está no CSV.
        if coluna.startswith("Prob") or coluna in ("LogLoss", "RPS"):
            tabela[coluna] = pd.to_numeric(tabela[coluna]).round(casas)
        elif coluna in ("PontosEsperados", "PosicaoMedia"):
            tabela[coluna] = pd.to_numeric(tabela[coluna]).round(2)
    return tabela


def dim_equipa(equipas, calendario):
    """Só as 18 equipas da época atual (as outras 12 não aparecem em nenhum facto)."""
    da_epoca = set(calendario["EquipaCasa"]) | set(calendario["EquipaFora"])
    return equipas.loc[equipas["Equipa"].isin(da_epoca), ["Equipa", "NomeApresentacao", "EmblemaURL"]] \
        .sort_values("Equipa").reset_index(drop=True)


def dim_jornada(calendario, previsoes, classificacao):
    """Jornada 0 (início) a 34, com o dia do primeiro jogo (os jogos adiados não contam para a data)
    e o estado de cada jornada em relação à próxima: Jogada, Próxima ou Futura.
    Rotulo = "Próxima" na próxima jornada e "J1", "J2"... nas outras. É por este rótulo que se
    filtra no Power BI: um segmentador com "Próxima" selecionado salta sozinho para a jornada
    seguinte em cada atualização (o texto é sempre o mesmo, a jornada por trás é que muda).
     RotuloClassificacao = o mesmo truque para a página da classificação: "Atual" na última
    jornada que já tem classificação. TemClassificacao = 1 nas jornadas que já a têm (para
    o segmentador dessa página só mostrar essas)."""
    marcados = calendario[calendario["Estado"] != "POSTPONED"]
    inicio = pd.to_datetime(marcados.groupby("Jornada")["Data"].min())
    jornadas = pd.DataFrame({"Jornada": inicio.index.astype(int), "DataInicio": inicio.dt.date.to_numpy()})
    jornadas["NomeCurto"] = "J" + jornadas["Jornada"].astype(str)

    proximas = previsoes.loc[previsoes["Tipo"] == "Próxima jornada", "Jornada"]
    proxima = proximas.min() if len(proximas) else jornadas["Jornada"].max() + 1      # época acabada: todas jogadas
    jornadas["Estado"] = np.select([jornadas["Jornada"] < proxima, jornadas["Jornada"] == proxima],
                                   ["Jogada", "Próxima"], default="Futura")
    jornadas["Rotulo"] = np.where(jornadas["Estado"] == "Próxima", "Próxima", jornadas["NomeCurto"])

    ultima = classificacao["Jornada"].max() if len(classificacao) else 0
    jornadas["RotuloClassificacao"] = np.where(jornadas["Jornada"] == ultima, "Atual", jornadas["NomeCurto"])
    jornadas["TemClassificacao"] = jornadas["Jornada"].isin(classificacao["Jornada"]).astype(int)

    # Jornada 0 = antes do primeiro jogo: a mesma data da jornada 1
    inicio_epoca = pd.DataFrame({"Jornada": [0], "NomeCurto": ["Início"], "Rotulo": ["Início"], "Estado": ["Início"],
                                 "RotuloClassificacao": ["Início"], "TemClassificacao": [0],
                                 "DataInicio": [jornadas["DataInicio"].min()]})
    return pd.concat([inicio_epoca, jornadas], ignore_index=True)[
        ["Jornada", "NomeCurto", "Rotulo", "Estado", "RotuloClassificacao", "TemClassificacao", "DataInicio"]]


def dim_jogo(previsoes, equipas):
    """Um jogo por linha, com o resultado e o nome e emblema das duas equipas."""
    jogos = previsoes[["JogoID", "Jornada", "Data", "Hora", "EquipaCasa", "EquipaFora", "Estado", "Tipo",
                       "GolosCasa", "GolosFora", "Resultado", "FonteResultado"]].copy()
    for lado in ["Casa", "Fora"]:
        nomes = equipas.rename(columns={"Equipa": f"Equipa{lado}", "NomeApresentacao": f"Nome{lado}",
                                        "EmblemaURL": f"Emblema{lado}"})
        jogos = jogos.merge(nomes, on=f"Equipa{lado}", how="left", validate="many_to_one")
    jogos = jogos.sort_values(["Jornada", "Data", "Hora", "JogoID"]).reset_index(drop=True)
    jogos["OrdemJornada"] = jogos.groupby("Jornada").cumcount() + 1
    jogos["Data"] = pd.to_datetime(jogos["Data"]).dt.date
    jogos["Hora"] = pd.to_datetime(jogos["Hora"], format="%H:%M").dt.time
    for coluna in ["GolosCasa", "GolosFora"]:
        jogos[coluna] = jogos[coluna].astype("Int64")          # inteiro com vazios (jogos por jogar)
    return jogos


def com_acerto_inteiro(tabela):
    """O acerto vem como 1.0 / 0.0 / vazio; no warehouse é um inteiro."""
    return tabela.assign(Acerto=tabela["Acerto"].astype("Int64"))

# ---------------------------------------------------------------------
# EQUIPAS E JOGADORES (fichas da ESPN)
# ---------------------------------------------------------------------

def jogos_por_equipa(espn_jogos):
    """Cada jogo visto por cada uma das duas equipas: golos a favor, golos contra e duração."""
    colunas = ["JogoID", "Equipa", "GolosPro", "GolosContra", "Duracao"]
    casa = espn_jogos.assign(Equipa=espn_jogos["EquipaCasa"], GolosPro=espn_jogos["GolosCasa"],
                             GolosContra=espn_jogos["GolosFora"])[colunas]
    fora = espn_jogos.assign(Equipa=espn_jogos["EquipaFora"], GolosPro=espn_jogos["GolosFora"],
                             GolosContra=espn_jogos["GolosCasa"])[colunas]
    return pd.concat([casa, fora], ignore_index=True)


def fato_equipa_jogo(estatisticas, espn_jogos):
    """A posse e os passes de cada equipa em cada jogo, com os golos dela (para a eficiência)."""
    golos = jogos_por_equipa(espn_jogos)[["JogoID", "Equipa", "GolosPro"]].rename(columns={"GolosPro": "Golos"})
    tabela = estatisticas.merge(golos, on=["JogoID", "Equipa"], validate="one_to_one")
    contagens = [c for c in cfg.ESTATISTICAS_EQUIPA_ESPN.values() if c != "PosseBola"]
    tabela[["Golos"] + contagens] = tabela[["Golos"] + contagens].astype("Int64")
    return tabela[["JogoID", "Equipa", "Golos", "PosseBola"] + contagens]


def dim_jogador(jogadores):
    """Um jogador por linha. A linha (GR, DEF, MED, AV) é a posição em que a ESPN o pôs mais
    vezes; quem nunca teve posição (só "Substitute") fica "S/P". Os nomes têm de ser únicos,
    porque é pelo nome que o Power BI passa o jogador à descrição: se dois jogadores tiverem o
    mesmo nome, junta-se a equipa."""
    conhecidas = jogadores.dropna(subset=["Linha"])
    linha = conhecidas.groupby("JogadorID")["Linha"].agg(lambda posicoes: posicoes.mode().iloc[0])
    # O id do jogo na ESPN cresce com o tempo: fica-se com o último jogo de cada jogador
    ultimos = jogadores.sort_values("EventoID", key=lambda ids: ids.astype(int)).drop_duplicates("JogadorID", keep="last")
    tabela = ultimos[["JogadorID", "Nome", "Equipa"]].copy()
    tabela["Linha"] = tabela["JogadorID"].map(linha).fillna(cfg.LINHA_SEM_POSICAO)
    repetidos = tabela["Nome"].duplicated(keep=False)
    tabela.loc[repetidos, "Nome"] = tabela.loc[repetidos, "Nome"] + " (" + tabela.loc[repetidos, "Equipa"] + ")"
    return tabela[["JogadorID", "Nome", "Linha"]].sort_values("JogadorID").reset_index(drop=True)


def posicoes_no_plantel(minutos):
    """Espalha os jogadores de uma linha a partir do centro, os mais utilizados primeiro:
    0, -1, +1, -2, +2... (recebe os minutos já por ordem decrescente)."""
    return [((i + 1) // 2) * (-1 if i % 2 else 1) for i in range(len(minutos))]

def rotulo_no_campo(nome_curto, golos, assistencias, vermelhos):
    """O nome que aparece debaixo da bolinha, com o que o jogador fez no jogo:
    "T. Araújo", 2 golos e 1 assistência -> "T. Araújo ⚽⚽🅰"; expulso -> "... 🟥"."""
    def vezes(valor):
        return 0 if pd.isna(valor) else int(valor)
    icones = "⚽" * vezes(golos) + "🅰" * vezes(assistencias) + "🟥" * min(vezes(vermelhos), 1)
    return f"{nome_curto} {icones}" if icones else nome_curto


def fato_jogador_jogo(jogadores):
    """Um jogador por jogo: titular ou suplente, quando entrou e saiu, quem substituiu, o lugar no
    campo (só os titulares) e o que fez nesse jogo. É o que o campo da página da Equipa mostra.
    O Rotulo é o texto debaixo da bolinha: tem de ser único dentro de cada jogo e equipa (é por
    ele que o Power BI distingue as bolinhas); se dois colegas tiverem o mesmo nome curto,
    usa-se o nome completo."""
    colunas = ["JogoID", "JogadorID", "Equipa", "Rotulo", "Formacao", "PosicaoCurta", "Titular", "Entrou", "Saiu",
               "Minutos", "Substituiu", "CampoX", "CampoY", "Golos", "Assistencias", "Amarelos", "Vermelhos"]
    tabela = jogadores.copy()
    repetido = tabela.duplicated(["JogoID", "Equipa", "NomeCurto"], keep=False)
    nome = tabela["NomeCurto"].where(~repetido, tabela["Nome"])
    tabela["Rotulo"] = [rotulo_no_campo(n, g, a, v) for n, g, a, v in
                        zip(nome, tabela["Golos"], tabela["Assistencias"], tabela["Vermelhos"])]
    tabela = tabela[colunas]
    inteiros = ["CampoX", "CampoY", "Golos", "Assistencias", "Amarelos", "Vermelhos"]
    tabela[inteiros] = tabela[inteiros].astype("Int64")
    return tabela

def fato_jogador_epoca(jogadores, espn_jogos, dim_jogadores):
    """A época de cada jogador em cada equipa: totais, função, impacto e o lugar da bolinha no plantel.
    O impacto compara o saldo de golos da equipa por 90 minutos com ele em campo e sem ele."""
    estatisticas = list(cfg.ESTATISTICAS_JOGADOR_ESPN.values())
    equipa = jogos_por_equipa(espn_jogos).groupby("Equipa").agg(
        GolosProEquipa=("GolosPro", "sum"), GolosContraEquipa=("GolosContra", "sum"), MinutosEquipa=("Duracao", "sum"))
    por_jogo = jogadores.assign(
        Jogou=(jogadores["Minutos"] > 0).astype(int),
        SemSofrer=((jogadores["Linha"] == "GR") & (jogadores["Minutos"] >= 60)
                   & (jogadores["GolosContraEmCampo"] == 0)).astype(int))
    tabela = por_jogo.groupby(["JogadorID", "Equipa"], as_index=False).agg(
        Convocatorias=("JogoID", "nunique"), Jogos=("Jogou", "sum"), Titularidades=("Titular", "sum"),
        Minutos=("Minutos", "sum"), GolosProEmCampo=("GolosProEmCampo", "sum"),
        GolosContraEmCampo=("GolosContraEmCampo", "sum"), JogosSemSofrer=("SemSofrer", "sum"),
        **{coluna: (coluna, "sum") for coluna in estatisticas})
    tabela[estatisticas] = tabela[estatisticas].astype(int)
    tabela = tabela.merge(equipa, on="Equipa", validate="many_to_one")

    tabela["PercMinutos"] = tabela["Minutos"] / tabela["MinutosEquipa"]
    tabela["Funcao"] = np.select(
        [tabela["Minutos"] == 0] + [tabela["PercMinutos"] >= limite for limite in cfg.FUNCOES_PLANTEL.values()],
        ["Sem minutos"] + list(cfg.FUNCOES_PLANTEL), default="Pouco utilizado")

    minutos_sem_ele = tabela["MinutosEquipa"] - tabela["Minutos"]
    com_ele = (tabela["GolosProEmCampo"] - tabela["GolosContraEmCampo"]) / tabela["Minutos"] * 90
    sem_ele = ((tabela["GolosProEquipa"] - tabela["GolosProEmCampo"])
               - (tabela["GolosContraEquipa"] - tabela["GolosContraEmCampo"])) / minutos_sem_ele * 90
    chega_com = tabela["Minutos"] >= cfg.MINUTOS_MINIMOS_IMPACTO
    chega_sem = minutos_sem_ele >= cfg.MINUTOS_MINIMOS_IMPACTO
    tabela["SaldoComEle90"] = com_ele.where(chega_com)
    tabela["SaldoSemEle90"] = sem_ele.where(chega_sem)
    tabela["Impacto90"] = (com_ele - sem_ele).where(chega_com & chega_sem)

    tabela = tabela.merge(dim_jogadores[["JogadorID", "Linha"]], on="JogadorID", validate="many_to_one")
    tabela = tabela.sort_values(["Equipa", "Linha", "Minutos"], ascending=[True, True, False])
    tabela["PlantelX"] = tabela.groupby(["Equipa", "Linha"])["Minutos"].transform(
        lambda minutos: posicoes_no_plantel(minutos))
    tabela["PlantelY"] = tabela["Linha"].map(cfg.PLANTEL_Y)
    tabela["Minutos"] = tabela["Minutos"].round().astype(int)
    tabela[["PercMinutos", "SaldoComEle90", "SaldoSemEle90", "Impacto90"]] = \
        tabela[["PercMinutos", "SaldoComEle90", "SaldoSemEle90", "Impacto90"]].round(cfg.CASAS_DECIMAIS)
    return tabela.drop(columns=["Linha", "GolosProEquipa", "GolosContraEquipa", "MinutosEquipa"]).reset_index(drop=True)


def fato_previsoes(previsoes):
    colunas = ["JogoID", "ProbCasa", "ProbEmpate", "ProbFora", "Previsto", "Acerto", "LogLoss", "RPS"] \
        + [c for c in previsoes.columns if c.startswith("Prob") and c not in ("ProbCasa", "ProbEmpate", "ProbFora")]
    return com_acerto_inteiro(arredondar(previsoes[colunas]))

def fato_epocas_equipa(jogos_anteriores, equipas):
    """A classificação final de cada época anterior, com as mesmas regras de desempate da
    classificação atual (simulacao.classificacao_atual). Só as equipas desta época, que são
    as que têm página no relatório."""
    partes = [simulacao.classificacao_atual(jogos.assign(Terminado=True)).assign(Epoca=epoca)
              for epoca, jogos in jogos_anteriores.groupby("Epoca")]
    tabela = pd.concat(partes, ignore_index=True)
    tabela = tabela[tabela["Equipa"].isin(equipas["Equipa"])]
    return tabela[["Epoca", "Equipa"] + COLUNAS_CLASSIFICACAO].reset_index(drop=True)

def fato_avaliacao_oficial(avaliacao):
    """Sem o DataCorte nem os dados do jogo (data, equipas, resultado): esses estão na dim_jogo."""
    colunas = ["JogoID", "ProbCasa", "ProbEmpate", "ProbFora", "Previsto", "Acerto", "LogLoss", "RPS",
               "ProbOddsCasa", "ProbOddsEmpate", "ProbOddsFora"]
    return com_acerto_inteiro(arredondar(avaliacao[colunas]))


def fato_simulacao(simulacao_epoca):
    return arredondar(simulacao_epoca[["Equipa"] + COLUNAS_CLASSIFICACAO + COLUNAS_SIMULACAO])


def fato_classificacao_jornada(classificacao):
    """A classificação depois de cada jornada, com quantos lugares cada equipa subiu (+) ou
    desceu (-) em relação à jornada anterior. Na jornada 1 fica vazio (não há anterior)."""
    tabela = classificacao[["Jornada", "Equipa"] + COLUNAS_CLASSIFICACAO].sort_values(["Equipa", "Jornada"])
    anterior = tabela.groupby("Equipa")["Posicao"].shift(1)          # a posição da mesma equipa na jornada antes
    tabela["VariacaoPosicao"] = (anterior - tabela["Posicao"]).astype("Int64")   # 5.º -> 3.º = +2 (subiu)
    return tabela.sort_values(["Jornada", "Posicao"]).reset_index(drop=True)


def fato_historico(historico):
    """Só as probabilidades e os pontos esperados: a classificação de cada jornada já está
    na fato_classificacao_jornada."""
    atual = historico[historico["Epoca"] == cfg.EPOCA_ATUAL]
    return arredondar(atual[["Jornada", "Equipa"] + COLUNAS_SIMULACAO])

def fato_estatisticas_jogo(jogos_epoca):
    """As estatísticas de cada jogo, vindos do CSV."""
    tabela = jogos_epoca[["JogoID"] + cfg.COLUNAS_ESTATISTICAS].copy()
    tabela[cfg.COLUNAS_ESTATISTICAS] = tabela[cfg.COLUNAS_ESTATISTICAS].astype("Int64")  # inteiros com vazios
    return tabela

def tabela_atualizacao(calendario, ultimo_jogo_csv, calendario_descarregado_em, carregado_em):
    """Uma só linha com as datas que dizem "isto é de quando": quando o warehouse foi carregado,
    quando o calendário foi descarregado da API, o último jogo terminado (API) e o último jogo
    com estatísticas e odds (CSV)."""
    terminados = calendario.loc[calendario["Estado"] == "FINISHED", "Data"]
    return pd.DataFrame({
        "CarregadoEm": [pd.Timestamp(carregado_em).floor("s")],
        # errors="coerce": se a data no ficheiro não for válida, fica vazia em vez de parar o carregamento
        "CalendarioDescarregadoEm": [pd.to_datetime(calendario_descarregado_em, errors="coerce")],
        "UltimoJogoTerminado": [pd.to_datetime(terminados).max().date() if len(terminados) else None],
        "UltimoJogoCSV": [pd.to_datetime(ultimo_jogo_csv).date() if ultimo_jogo_csv else None],
    })

# ---------------------------------------------------------------------
# Avaliação dos modelos e calibração
# ---------------------------------------------------------------------

RESULTADOS = {"Casa": ("ProbH", "H"), "Empate": ("ProbD", "D"), "Fora": ("ProbA", "A")}


def preparar_avaliacao(tabela):
    """Junta os nomes ("Ordinal + DC + GB" passa a "Modelo final") e fica só com os 7 modelos do relatório."""
    tabela = tabela.assign(Modelo=tabela["Modelo"].replace(cfg.NOMES_MODELOS))
    return tabela[tabela["Modelo"].isin(cfg.MODELOS_AVALIACAO)].reset_index(drop=True)


def dim_fase(previsoes):
    """Validação e Teste, por ordem, com as épocas de cada uma ("21-22 a 24-25")."""
    epocas = previsoes.groupby("Fase")["Epoca"].agg(["min", "max"])
    fases = pd.DataFrame({"Fase": list(cfg.FICHEIROS_AVALIACAO)})
    fases["Ordem"] = range(1, len(fases) + 1)
    fases["Epocas"] = [epocas.loc[f, "min"] if epocas.loc[f, "min"] == epocas.loc[f, "max"]
                       else f"{epocas.loc[f, 'min']} a {epocas.loc[f, 'max']}" for f in fases["Fase"]]
    return fases


def dim_modelo():
    modelos = pd.DataFrame({"Modelo": list(cfg.MODELOS_AVALIACAO), "Grupo": list(cfg.MODELOS_AVALIACAO.values())})
    modelos["Ordem"] = range(1, len(modelos) + 1)
    return modelos


def intervalo_bootstrap(diferencas, semente=cfg.SEMENTE):
    """Intervalo de 95% da diferença média: sorteia os jogos com repetição muitas vezes e vê
    entre que valores cai a média em 95% das vezes."""
    gerador = np.random.default_rng(semente)
    sorteios = gerador.integers(0, len(diferencas), size=(cfg.REPETICOES_BOOTSTRAP, len(diferencas)))
    return np.percentile(diferencas[sorteios].mean(axis=1), [2.5, 97.5])


def fato_avaliacao_modelos(previsoes, resumos):
    """Uma linha por fase e modelo: as medidas e a diferença de log loss para as odds de abertura,
    jogo a jogo, com o intervalo do bootstrap (se o intervalo passa pelo 0, pode ser sorte)."""
    linhas = []
    for fase, grupo in previsoes.groupby("Fase", sort=False):
        log_loss = grupo.pivot(index="JogoID", columns="Modelo", values="LogLoss")
        for modelo in log_loss.columns:
            diferencas = (log_loss[modelo] - log_loss[cfg.MODELO_REFERENCIA]).to_numpy()
            inferior, superior = intervalo_bootstrap(diferencas)
            linhas.append({"Fase": fase, "Modelo": modelo, "DifReferencia": diferencas.mean(),
                           "DifInferior": inferior, "DifSuperior": superior})
    medias = previsoes.groupby(["Fase", "Modelo"], as_index=False).agg(
        Jogos=("JogoID", "size"), Acerto=("Acerto", "mean"), LogLoss=("LogLoss", "mean"), RPS=("RPS", "mean"))
    tabela = medias.merge(pd.DataFrame(linhas), on=["Fase", "Modelo"], validate="one_to_one") \
        .merge(resumos[["Fase", "Modelo", "ECE"]], on=["Fase", "Modelo"], how="left", validate="one_to_one")
    colunas = ["Acerto", "LogLoss", "RPS", "ECE", "DifReferencia", "DifInferior", "DifSuperior"]
    tabela[colunas] = tabela[colunas].round(cfg.CASAS_DECIMAIS)
    return tabela


def fato_avaliacao_epocas(previsoes):
    """Uma linha por fase, época e modelo (para a linha do tempo, época a época)."""
    tabela = previsoes.groupby(["Fase", "Epoca", "Modelo"], as_index=False).agg(
        Jogos=("JogoID", "size"), Acerto=("Acerto", "mean"), LogLoss=("LogLoss", "mean"), RPS=("RPS", "mean"))
    tabela[["Acerto", "LogLoss", "RPS"]] = tabela[["Acerto", "LogLoss", "RPS"]].round(cfg.CASAS_DECIMAIS)
    return tabela


def fato_calibracao(previsoes):
    """Para cada resultado (casa, empate, fora) em separado, como no ECE dos notebooks: os jogos
    juntam-se por faixas da probabilidade prevista e compara-se a média prevista com o que
    aconteceu. Ex.: faixa 70-80% da casa, previsto em média 75%, a casa ganhou 63%."""
    partes = []
    for resultado, (coluna, letra) in RESULTADOS.items():
        partes.append(pd.DataFrame({
            "Fase": previsoes["Fase"], "Modelo": previsoes["Modelo"], "Resultado": resultado,
            "Prob": previsoes[coluna], "Aconteceu": (previsoes["Resultado"] == letra).astype(int)}))
    longa = pd.concat(partes, ignore_index=True)
    # 0.37 -> faixa 3 (30-40%); o mínimo garante que 100% fica na última faixa
    longa["Faixa"] = np.minimum((longa["Prob"] * cfg.FAIXAS_CALIBRACAO).astype(int), cfg.FAIXAS_CALIBRACAO - 1)
    tabela = longa.groupby(["Fase", "Modelo", "Resultado", "Faixa"], as_index=False).agg(
        ProbMedia=("Prob", "mean"), FreqObservada=("Aconteceu", "mean"), Jogos=("Prob", "size"))
    tabela = tabela[tabela["Jogos"] >= cfg.MINIMO_JOGOS_FAIXA].reset_index(drop=True)
    largura = 100 // cfg.FAIXAS_CALIBRACAO
    tabela["RotuloFaixa"] = [f"{f * largura}-{(f + 1) * largura}%" for f in tabela["Faixa"]]
    tabela[["ProbMedia", "FreqObservada"]] = tabela[["ProbMedia", "FreqObservada"]].round(cfg.CASAS_DECIMAIS)
    return tabela


def tabelas_gold(fontes):
    """fontes = tabelas do SQLite (equipas, calendario, previsoes, avaliacao_oficial, simulacao_epoca,
    simulacao_posicoes, classificacao_jornada, historico). Devolve as tabelas do warehouse, pela
    ordem em que têm de ser carregadas (as dimensões antes dos factos, por causa das chaves)."""
    equipas = dim_equipa(fontes["equipas"], fontes["calendario"])
    jogadores = dim_jogador(fontes["jogadores_jogo"])
    previsoes_notebooks = preparar_avaliacao(fontes["previsoes_notebooks"])
    resumos_notebooks = preparar_avaliacao(fontes["resumos_notebooks"])
    return {
        "dEquipa": equipas,
        "dJornada": dim_jornada(fontes["calendario"], fontes["previsoes"], fontes["classificacao_jornada"]),
        "dJogo": dim_jogo(fontes["previsoes"], equipas),
        "fPrevisoes": fato_previsoes(fontes["previsoes"]),
        "fAvaliacao_oficial": fato_avaliacao_oficial(fontes["avaliacao_oficial"]),
        "fEstatisticas_jogo": fato_estatisticas_jogo(fontes["jogos_epoca"]),
        "fEpocas_equipa": fato_epocas_equipa(fontes["jogos_anteriores"], equipas),
        "fEquipa_jogo": fato_equipa_jogo(fontes["estatisticas_equipa_espn"], fontes["espn_jogos"]),
        "dJogador": jogadores,
        "fJogador_epoca": fato_jogador_epoca(fontes["jogadores_jogo"], fontes["espn_jogos"], jogadores),
        "fJogador_jogo": fato_jogador_jogo(fontes["jogadores_jogo"]),
        "fSimulacao": fato_simulacao(fontes["simulacao_epoca"]),
        "fPosicoes": arredondar(fontes["simulacao_posicoes"][["Equipa", "Posicao", "Probabilidade"]]),
        "fClassificacao_jornada": fato_classificacao_jornada(fontes["classificacao_jornada"]),
        "fHistorico": fato_historico(fontes["historico"]),
        "dFase": dim_fase(previsoes_notebooks),
        "dModelo": dim_modelo(),
        "fAvaliacao_modelos": fato_avaliacao_modelos(previsoes_notebooks, resumos_notebooks),
        "fAvaliacao_epocas": fato_avaliacao_epocas(previsoes_notebooks),
        "fCalibracao": fato_calibracao(previsoes_notebooks),
        "fAtualizacao": tabela_atualizacao(fontes["calendario"], fontes["ultimo_jogo_csv"],
                                          fontes["calendario_descarregado_em"], fontes["carregado_em"]),

    }

# ---------------------------------------------------------------------
# CARREGAMENTO
# ---------------------------------------------------------------------

class CargaIncompleta(Exception):
    """Uma tabela do warehouse ficou com linhas diferentes das que saíram do Python."""


def carregar(tabelas, motor, caminho_esquema=cfg.ESQUEMA_WAREHOUSE_SQL, esquema=cfg.ESQUEMA_GOLD):
    """Apaga e cria as tabelas e carrega-as, TUDO numa transação: se algo falhar (uma chave
    que não bate certo, um tipo errado, linhas a menos), o PostgreSQL desfaz tudo e fica a
    versão anterior. Devolve {tabela: linhas no warehouse}."""
    with motor.begin() as ligacao:          # begin(): commit no fim, rollback se der erro
        ligacao.exec_driver_sql(caminho_esquema.read_text(encoding="utf-8"))
        for nome, tabela in tabelas.items():
            tabela.to_sql(nome, ligacao, schema=esquema, if_exists="append", index=False)
        # Contadas ANTES do commit: se não baterem certo, a exceção desfaz o carregamento
        linhas = {nome: ligacao.execute(text(f'SELECT COUNT(*) FROM {esquema}."{nome}"')).scalar() for nome in tabelas}
        diferentes = {nome: (len(tabelas[nome]), n) for nome, n in linhas.items() if n != len(tabelas[nome])}
        if diferentes:
            raise CargaIncompleta(f"(esperadas, carregadas): {diferentes}")
    return linhas