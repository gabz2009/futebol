"""
=====================================================================
 CONFIGURAÇÃO DO ETL
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   Tudo o que pode mudar de um ano para o outro está aqui: pastas,
   épocas, nomes de colunas e regras. Os outros ficheiros só leem
   estes valores. Assim, para acrescentar uma época nova, só se mexe
   neste ficheiro.
=====================================================================
"""
from pathlib import Path

# ---------------------------------------------------------------
# PASTAS E FICHEIROS
# ---------------------------------------------------------------
# Pasta do projeto = a pasta acima de "etl"
PASTA_PROJETO = Path(__file__).resolve().parent.parent

PASTA_ORIGEM = PASTA_PROJETO / "dados" / "origem"       # CSV descarregados
BASE_DADOS = PASTA_PROJETO / "dados" / "futebol.db"     # base de dados SQLite
FICHEIRO_LOG = PASTA_PROJETO / "dados" / "etl.log"

# Os ficheiros têm de se chamar P1_2017-18.csv, P1_2018-19.csv, ...
# A época é lida do próprio nome do ficheiro.
PADRAO_FICHEIROS = "P1_*.csv"

# ---------------------------------------------------------------
# ÉPOCAS
# ---------------------------------------------------------------
EPOCAS_ESPERADAS = ["17-18", "18-19", "19-20", "20-21", "21-22",
                    "22-23", "23-24", "24-25", "25-26", "26-27"]

# A época atual ainda está a decorrer, por isso não tem 306 jogos
EPOCA_ATUAL = "26-27"

NUM_EQUIPAS = 18
JOGOS_POR_EPOCA = NUM_EQUIPAS * (NUM_EQUIPAS - 1)       # 18 x 17 = 306
JOGOS_POR_EQUIPA = (NUM_EQUIPAS - 1) * 2                # 34

MES_INICIO_EPOCA = 8

# Épocas jogadas sem público ou com público limitado (COVID)
EPOCAS_COVID = ["19-20", "20-21"]

# ---------------------------------------------------------------
# COLUNAS
# ---------------------------------------------------------------
# 1) Nomes antigos que mudaram a partir de 2019-20.
#    Em 2017-18 e 2018-19 as odds médias e máximas vinham do Betbrain
#    (Bb...). Depois passaram a chamar-se Avg... e Max...
MAPA_NOMES_ANTIGOS = {
    "BbAvH": "AvgH", "BbAvD": "AvgD", "BbAvA": "AvgA",
    "BbMxH": "MaxH", "BbMxD": "MaxD", "BbMxA": "MaxA",
}

# 2) Colunas que ficam no modelo e o seu nome em português.
#    Tudo o que não está aqui é ignorado.
COLUNAS_FINAIS = {
    "Date": "Data",
    "Time": "Hora",
    "HomeTeam": "EquipaCasa",
    "AwayTeam": "EquipaFora",
    "FTHG": "GolosCasa",
    "FTAG": "GolosFora",
    "FTR": "Resultado",
    "HTHG": "GolosCasaIntervalo",
    "HTAG": "GolosForaIntervalo",
    "HTR": "ResultadoIntervalo",
    "HS": "RematesCasa",
    "AS": "RematesFora",
    "HST": "RematesBalizaCasa",
    "AST": "RematesBalizaFora",
    "HF": "FaltasCasa",
    "AF": "FaltasFora",
    "HC": "CantosCasa",
    "AC": "CantosFora",
    "HY": "AmarelosCasa",
    "AY": "AmarelosFora",
    "HR": "VermelhosCasa",
    "AR": "VermelhosFora",
    "B365H": "OddCasaB365",
    "B365D": "OddEmpateB365",
    "B365A": "OddForaB365",
    "AvgH": "OddCasaMedia",
    "AvgD": "OddEmpateMedia",
    "AvgA": "OddForaMedia",
    "B365CH": "OddCasaFechoB365",
    "B365CD": "OddEmpateFechoB365",
    "B365CA": "OddForaFechoB365",
    "AvgCH": "OddCasaFechoMedia",
    "AvgCD": "OddEmpateFechoMedia",
    "AvgCA": "OddForaFechoMedia"
}

# 3) Colunas que podem não existir em todas as épocas.
#    Se faltarem, a coluna é criada vazia em vez de parar o ETL.
#    (A hora do jogo só existe a partir de 2019-20.)
COLUNAS_OPCIONAIS = ["Time", "B365CH", "B365CD", "B365CA", "AvgCH", "AvgCD", "AvgCA"]

# Colunas numéricas inteiras (golos, remates, cartões...)
COLUNAS_INTEIRAS = ["GolosCasa", "GolosFora", "GolosCasaIntervalo", "GolosForaIntervalo",
                    "RematesCasa", "RematesFora", "RematesBalizaCasa", "RematesBalizaFora",
                    "FaltasCasa", "FaltasFora", "CantosCasa", "CantosFora",
                    "AmarelosCasa", "AmarelosFora", "VermelhosCasa", "VermelhosFora"]

COLUNAS_ODDS = ["OddCasaB365", "OddEmpateB365", "OddForaB365",
                "OddCasaMedia", "OddEmpateMedia", "OddForaMedia"]

COLUNAS_ODDS_FECHO = ["OddCasaFechoB365", "OddEmpateFechoB365", "OddForaFechoB365",
                     "OddCasaFechoMedia", "OddEmpateFechoMedia", "OddForaFechoMedia"]

COLUNAS_RASTREIO = ["Epoca", "Ficheiro", "LinhaOrigem"]

VARIAVEIS_FORA_DO_MODELO = {"CasaJogosNaEpoca", "ForaJogosNaEpoca", "EpocaCOVID",
                            "CasaDiasDescanso", "ForaDiasDescanso", "DifDiasDescanso"}

COLUNAS_ESTATISTICAS = ["GolosCasaIntervalo", "GolosForaIntervalo", "RematesCasa", "RematesFora",
                        "RematesBalizaCasa", "RematesBalizaFora", "CantosCasa", "CantosFora",
                        "FaltasCasa", "FaltasFora", "AmarelosCasa", "AmarelosFora", "VermelhosCasa", "VermelhosFora"]

MARGEM_MIN = 1.00
MARGEM_MAX = 1.15

RESULTADOS_VALIDOS = ["H", "D", "A"]     # casa, empate, fora

# ---------------------------------------------------------------
# CALENDÁRIO EPOCA ATUAL
# ---------------------------------------------------------------

API_URL = "https://api.football-data.org/v4/competitions/PPL/matches"
API_EPOCA = 2026                     # a API identifica a época pelo ano em que começa
FICHEIRO_CHAVE = PASTA_PROJETO / ".env"
FICHEIRO_CALENDARIO = PASTA_ORIGEM / f"calendario_{EPOCA_ATUAL}.json"

NOMES_API = {
    "Sport Lisboa e Benfica": "Benfica", "FC Porto": "Porto", "Sporting Clube de Portugal": "Sp Lisbon",
    "Sporting Clube de Braga": "Sp Braga", "Vitória SC": "Guimaraes", "FC Famalicão": "Famalicao",
    "Gil Vicente FC": "Gil Vicente", "Moreirense FC": "Moreirense", "Rio Ave FC": "Rio Ave",
    "Casa Pia AC": "Casa Pia", "GD Estoril Praia": "Estoril", "CD Santa Clara": "Santa Clara",
    "CD Nacional": "Nacional", "FC Arouca": "Arouca", "CF Estrela da Amadora": "Estrela",
    "FC Alverca": "Alverca", "CS Marítimo": "Maritimo", "Académico de Viseu FC": "Academico Viseu",
}

# ---------------------------------------------------------------
# EQUIPAS
# ---------------------------------------------------------------
NOTAS_EQUIPAS = {
    "Aves": "Desportivo das Aves. Não é a mesma entidade que o AVS.",
    "AVS": "AVS Futebol SAD, criada em 2023. Não é a continuação do Desportivo das Aves.",
}

NOMES_APRESENTACAO = {
    "Academico Viseu": "Académico de Viseu", "Alverca": "FC Alverca",
    "Arouca": "FC Arouca", "Aves": "CD Aves", "AVS": "AVS Futebol",
    "Belenenses": "Belenenses SAD", "Benfica": "SL Benfica", "Boavista": "Boavista FC",
    "Casa Pia": "Casa Pia AC", "Chaves": "GD Chaves", "Estoril": "Estoril Praia",
    "Estrela": "Estrela da Amadora", "Famalicao": "FC Famalicão", "Farense": "SC Farense",
    "Feirense": "CD Feirense", "Gil Vicente": "Gil Vicente FC", "Guimaraes": "Vitória SC",
    "Maritimo": "CS Marítimo", "Moreirense": "Moreirense FC", "Nacional": "CD Nacional",
    "Pacos Ferreira": "FC Paços de Ferreira", "Portimonense": "Portimonense SC",
    "Porto": "FC Porto", "Rio Ave": "Rio Ave FC", "Santa Clara": "CD Santa Clara",
    "Setubal": "Vitória FC", "Sp Braga": "SC Braga", "Sp Lisbon": "Sporting CP",
    "Tondela": "CD Tondela", "Vizela": "FC Vizela",
}

# ---------------------------------------------------------------
# SQLITE e PostgreSQL
# ---------------------------------------------------------------
ESQUEMA_SQL = PASTA_PROJETO / "etl" / "esquema.sql"

ESQUEMA_SQL_VARIAVEIS = PASTA_PROJETO / "etl" / "esquema_variaveis.sql"

VARIAVEIS_POSTGRES = ["PG_HOST", "PG_PORTA", "PG_BASE", "PG_UTILIZADOR", "PG_PALAVRA_PASSE"]

ESQUEMA_GOLD = "gold"

ESQUEMA_WAREHOUSE_SQL = PASTA_PROJETO / "etl" / "esquema_warehouse.sql"

CASAS_DECIMAIS = 4
# ---------------------------------------------------------------
# ML
# ---------------------------------------------------------------
JANELA_FORMA = 5

DESCANSO_MAX = 14

ELO_INICIAL = 1500

ELO_K = 20

ELO_VANTAGEM_CASA = 60

ELO_REGRESSAO = 0.20

USO_EPOCA = {
    "17-18": "Aquecimento",
    "18-19": "Treino", "19-20": "Treino", "20-21": "Treino",
    "21-22": "Validação", "22-23": "Validação", "23-24": "Validação", "24-25": "Validação",
    "25-26": "Teste",
    "26-27": "Previsão",
}

PI_LAMBDA = 0.035
PI_GAMMA = 0.7
PI_BASE = 10
PI_C = 3

GAP_AFINACAO = ["Treino", "Validação"]

GAP_PARAMETROS = {
    "Falhados": {"casa": "RematesFalhadosCasa", "fora": "RematesFalhadosFora", "lambda": 0.2, "phi1": 0.6, "phi2": 0.5},
    "Baliza": {"casa": "RematesBalizaCasa", "fora": "RematesBalizaFora", "lambda": 0.15, "phi1": 0.6, "phi2": 0.5},
    "Cantos": {"casa": "CantosCasa", "fora": "CantosFora", "lambda": 0.1, "phi1": 0.6, "phi2": 0.6},
}

ESTATISTICAS = {
    "Falhados": ("RematesFalhadosCasa", "RematesFalhadosFora"),
    "Baliza": ("RematesBalizaCasa", "RematesBalizaFora"),
    "Cantos": ("CantosCasa", "CantosFora"),
}
GRELHA_LAMBDA = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
GRELHA_PHI = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

# ---------------------------------------------------------------
# ML -- Modelos
# ---------------------------------------------------------------

DC_XI = 0.001
DC_RIDGE = 2
DC_DIAS_REAJUSTE = 7 
DC_MAX_GOLOS = 10

GB_GRELHA = {
    "learning_rate": [0.01, 0.02, 0.05],
    "max_depth": [1, 2, 3],
    "max_iter": [10, 25, 50,100, 200],
    "min_samples_leaf": [50, 100, 200],
}

GB_EPOCAS_AFINACAO = 2

COLUNAS_ORDINAL = ["GapFalhadosDif", "GapBalizaDif", "GapCantosDif"]



ESQUEMA_PREVISOES_SQL = PASTA_PROJETO / "etl" / "esquema_previsoes.sql"

SIMULACOES = 10_000
INICIO_PREVISOES_REAIS = "2026-10-30"
SEMENTE = 42

ZONAS_CLASSIFICACAO = {
    "Campeao": (1, 1),
    "Top3": (1, 3),
    "Europa": (1, 5),
    "PlayoffDescida": (16, 16),
    "Descida": (17, 18),
}

BASE_HISTORICO = PASTA_PROJETO / "dados" / "historico.db"
ESQUEMA_HISTORICO_SQL = PASTA_PROJETO / "etl" / "esquema_historico.sql"

# ---------------------------------------------------------------
# EMBLEMAS CLUBES
# ---------------------------------------------------------------

THESPORTSDB_URL = "https://www.thesportsdb.com/api/v1/json/123/searchteams.php"
FICHEIRO_EMBLEMAS = PASTA_ORIGEM / "emblemas_thesportsdb.json"

# Nome usado na pesquisa no TheSportsDB (quando é diferente do nosso)
NOMES_THESPORTSDB = {
    "Guimaraes": "Vitoria Guimaraes", "Setubal": "Vitoria Setubal", "Sp Braga": "Braga",
    "Sp Lisbon": "Sporting CP", "Estrela": "Estrela Amadora", "Nacional": "Nacional de Madeira"
}

EMBLEMAS_MANUAIS = {}

# ---------------------------------------------------------------
# Ficheiro football data uk
# ---------------------------------------------------------------

# CSV da época atual no football-data.co.uk (2026-27 -> pasta "2627"). Se o site mudar o endereço, é só aqui.
CSV_URL = f"https://football-data.co.uk/mmz4281/2627/P1.csv"
FICHEIRO_CSV_ATUAL = PASTA_ORIGEM / f"P1_{EPOCA_ATUAL}.csv"
# Colunas sem as quais o ficheiro descarregado é recusado (o resto é verificado pelo ETL, no C02)
COLUNAS_MINIMAS_CSV = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]

# ---------------------------------------------------------------
# Tabelas de comparação do warehouse
# ---------------------------------------------------------------

# Avaliação dos notebooks (página "Como o modelo foi avaliado" do relatório).
# Os CSV que os notebooks 02 (validação) e 03 (teste) guardaram: as previsões jogo a jogo e o resumo.
PASTA_AVALIACAO = PASTA_PROJETO / "dados"
FICHEIROS_AVALIACAO = {
    "Validação": ("previsoes_validacao.csv", "resumo_validacao.csv"),
    "Teste": ("previsoes_teste.csv", "resumo_teste.csv"),
}
# Na validação o modelo final ainda não se chamava assim
NOMES_MODELOS = {"Ordinal + DC + GB": "Modelo final"}
# Os 7 modelos que existem nas duas fases, pela ordem do relatório, e o grupo de cada um
MODELOS_AVALIACAO = {
    "Modelo final": "Modelo",
    "Ordinal GAP": "Modelo",
    "Dixon-Coles": "Modelo",
    "Boosting": "Modelo",
    "Odds de abertura": "Casas de apostas",
    "Odds de fecho": "Casas de apostas",
    "Frequências": "Referência",
}
MODELO_REFERENCIA = "Odds de abertura"     # o torneio mede a diferença de cada modelo para este
REPETICOES_BOOTSTRAP = 2000
FAIXAS_CALIBRACAO = 10                     # faixas de 10%: 0-10%, 10-20%, ..., 90-100%
MINIMO_JOGOS_FAIXA = 20                    # com menos jogos, a faixa salta ao acaso (como no notebook)

# ---------------------------------------------------------------
# ESPN dataset
# ---------------------------------------------------------------

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/por.1"
ESPN_USER_AGENT = "Mozilla/5.0 (projeto pessoal de portefolio)"
ESPN_PAUSA = 1                       # segundos entre pedidos: a API não é pública, não se abusa
PASTA_ESPN = PASTA_ORIGEM / "espn"

ESTATISTICAS_JOGADOR_ESPN = {
    "totalGoals": "Golos", "goalAssists": "Assistencias", "ownGoals": "Autogolos",
    "totalShots": "Remates", "shotsOnTarget": "RematesBaliza",
    "foulsCommitted": "FaltasCometidas", "foulsSuffered": "FaltasSofridas", "offsides": "ForasDeJogo",
    "yellowCards": "Amarelos", "redCards": "Vermelhos",
    "saves": "Defesas", "shotsFaced": "RematesEnfrentados", "goalsConceded": "GolosSofridos",
}
ESTATISTICAS_EQUIPA_ESPN = {
    "possessionPct": "PosseBola", "accuratePasses": "PassesCertos", "totalPasses": "Passes",
    "accurateCrosses": "CruzamentosCertos", "totalCrosses": "Cruzamentos",
    "accurateLongBalls": "PassesLongosCertos", "totalLongBalls": "PassesLongos",
    "totalShots": "Remates", "shotsOnTarget": "RematesBaliza",
}
# A linha de cada jogador (para o plantel), pela posição que a ESPN lhe dá em cada jogo
LINHAS_ESPN = {"Goalkeeper": "GR", "Defender": "DEF", "Back": "DEF", "Midfielder": "MED",
               "Forward": "AV", "Striker": "AV", "Winger": "AV"}
# Plantel (página da Equipa). A função de cada jogador vem da parte dos minutos da equipa que
# ele jogou: a partir de 70% é titular habitual, a partir de 30% é rotação, abaixo é pouco utilizado
FUNCOES_PLANTEL = {"Titular habitual": 0.70, "Rotação": 0.30}
MINUTOS_MINIMOS_IMPACTO = 450        # 5 jogos completos: com menos, o saldo com e sem ele é ruído
LINHA_SEM_POSICAO = "S/P"            # jogadores a quem a ESPN nunca deu posição (só "Substitute")
# Altura de cada linha no gráfico do plantel (avançados em cima)
PLANTEL_Y = {"AV": 5, "MED": 4, "DEF": 3, "GR": 2, LINHA_SEM_POSICAO: 1}

# Onde fica cada titular no campo (página da Equipa), em % da largura (X, da esquerda para a direita)
# e do comprimento (Y, da nossa baliza para a do adversário). A ESPN dá o nome da posição
# conforme a formação (ex.: LM e RM são o "2" do 4-2-3-1, mas os alas do 3-4-3), por isso o
# lugar depende das duas. Confirmado nas fichas: cada formação tem exatamente estas 11 posições.
_DEFESA_4 = {"G": (50, 6), "LB": (14, 26), "CD-L": (37, 22), "CD-R": (63, 22), "RB": (86, 26)}
_DEFESA_3 = {"G": (50, 6), "CD-L": (28, 22), "CD": (50, 20), "CD-R": (72, 22)}
_MEIO_4 = {"LM": (12, 50), "CM-L": (38, 46), "CM-R": (62, 46), "RM": (88, 50)}
CAMPO_POR_FORMACAO = {
    "4-2-3-1": _DEFESA_4 | {"LM": (36, 44), "RM": (64, 44), "AM-L": (16, 66), "AM": (50, 64), "AM-R": (84, 66), "F": (50, 84)},
    "4-3-3": _DEFESA_4 | {"LM": (26, 48), "CM": (50, 44), "RM": (74, 48), "LF": (18, 78), "F": (50, 84), "RF": (82, 78)},
    "3-4-3": _DEFESA_3 | _MEIO_4 | {"CF-L": (20, 78), "F": (50, 84), "CF-R": (80, 78)},
    "3-4-2-1": _DEFESA_3 | _MEIO_4 | {"CF-L": (34, 68), "CF-R": (66, 68), "F": (50, 84)},
    "4-1-4-1": _DEFESA_4 | {"DM": (50, 36)} | {"LM": (14, 56), "CM-L": (37, 54), "CM-R": (63, 54), "RM": (86, 56), "F": (50, 84)},
    "5-4-1": {"G": (50, 6), "LB": (10, 30), "CD-L": (30, 22), "CD": (50, 20), "CD-R": (70, 22), "RB": (90, 30)}
             | _MEIO_4 | {"F": (50, 82)},
    "4-5-1": _DEFESA_4 | {"LM": (12, 52), "CM-L": (32, 48), "AM": (50, 58), "CM-R": (68, 48), "RM": (88, 52), "F": (50, 84)},
}