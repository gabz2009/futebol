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
# SQLITE
# ---------------------------------------------------------------
ESQUEMA_SQL = PASTA_PROJETO / "etl" / "esquema.sql"

ESQUEMA_SQL_VARIAVEIS = PASTA_PROJETO / "etl" / "esquema_variaveis.sql"
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