-- =====================================================================
--  ESQUEMA DA BASE DE DADOS
-- =====================================================================
--  As tabelas são criadas aqui, com tipos, chaves primárias e chaves
--  estrangeiras. O Python só insere os dados.
--  Assim a própria base de dados recusa jogos repetidos (chave
--  primária) e equipas ou épocas que não existam (chaves estrangeiras).
--  É uma segunda linha de defesa, além dos controlos em Python.
-- =====================================================================

CREATE TABLE equipas (
    Equipa            TEXT PRIMARY KEY,     -- nome usado no site (ex.: Sp Lisbon)
    NomeApresentacao  TEXT NOT NULL,        -- nome a mostrar (ex.: Sporting CP)
    PrimeiraEpoca     TEXT NOT NULL,
    UltimaEpoca       TEXT NOT NULL,
    NumEpocas         INTEGER NOT NULL,
    Nota              TEXT
);

CREATE TABLE epocas (
    Epoca     TEXT PRIMARY KEY,             -- ex.: 2017-18
    Inicio    TEXT NOT NULL,                -- datas em texto ISO (2017-08-06)
    Fim       TEXT NOT NULL,
    Jogos     INTEGER NOT NULL,
    Completa  INTEGER NOT NULL,             -- 1 = sim, 0 = não
    Uso       TEXT NOT NULL,                -- Treino, Validação, Teste ou Previsão
    COVID     INTEGER NOT NULL
);

CREATE TABLE jogos (
    JogoID              TEXT PRIMARY KEY,   -- ex.: 2017-18_Aves_Sp Lisbon
    Epoca               TEXT NOT NULL REFERENCES epocas (Epoca),
    Ficheiro            TEXT NOT NULL,
    LinhaOrigem         INTEGER NOT NULL,
    Data                TEXT NOT NULL,
    Hora                TEXT,               -- só existe a partir de 2019-20
    EquipaCasa          TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora          TEXT NOT NULL REFERENCES equipas (Equipa),
    GolosCasa           INTEGER NOT NULL,
    GolosFora           INTEGER NOT NULL,
    Resultado           TEXT NOT NULL CHECK (Resultado IN ('H', 'D', 'A')),
    GolosCasaIntervalo  INTEGER NOT NULL,
    GolosForaIntervalo  INTEGER NOT NULL,
    ResultadoIntervalo  TEXT,
    RematesCasa         INTEGER NOT NULL,
    RematesFora         INTEGER NOT NULL,
    RematesBalizaCasa   INTEGER NOT NULL,
    RematesBalizaFora   INTEGER NOT NULL,
    FaltasCasa          INTEGER NOT NULL,
    FaltasFora          INTEGER NOT NULL,
    CantosCasa          INTEGER NOT NULL,
    CantosFora          INTEGER NOT NULL,
    AmarelosCasa        INTEGER NOT NULL,
    AmarelosFora        INTEGER NOT NULL,
    VermelhosCasa       INTEGER NOT NULL,
    VermelhosFora       INTEGER NOT NULL,
    OddCasaB365         REAL,               -- podem faltar (ver qa_odds_em_falta)
    OddEmpateB365       REAL,
    OddForaB365         REAL,
    OddCasaMedia        REAL,
    OddEmpateMedia      REAL,
    OddForaMedia        REAL,
    OddCasaFechoB365     REAL,
    OddEmpateFechoB365   REAL,
    OddForaFechoB365     REAL,
    OddCasaFechoMedia    REAL,
    OddEmpateFechoMedia  REAL,
    OddForaFechoMedia    REAL,
    TotalGolos          INTEGER NOT NULL,
    EpocaCOVID          INTEGER NOT NULL,
    UNIQUE (Ficheiro, LinhaOrigem)          -- cada linha de origem entra uma só vez
);

CREATE TABLE qa_controlos (
    Controlo   TEXT PRIMARY KEY,
    Descricao  TEXT NOT NULL,
    Esperado   TEXT,
    Obtido     TEXT,
    Estado     TEXT NOT NULL,               -- OK, AVISO ou FALHA
    Critico    INTEGER NOT NULL,
    Detalhe    TEXT
);

CREATE TABLE qa_odds_em_falta (
    JogoID          TEXT PRIMARY KEY REFERENCES jogos (JogoID),
    Epoca           TEXT NOT NULL,
    Data            TEXT NOT NULL,
    EquipaCasa      TEXT NOT NULL,
    EquipaFora      TEXT NOT NULL,
    OddCasaB365     REAL,
    OddEmpateB365   REAL,
    OddForaB365     REAL,
    OddCasaMedia    REAL,
    OddEmpateMedia  REAL,
    OddForaMedia    REAL
);

CREATE TABLE etl_execucoes (
    Inicio         TEXT PRIMARY KEY,        -- data e hora do início da execução
    Fim            TEXT NOT NULL,
    Estado         TEXT NOT NULL,           -- OK ou FALHA
    Ficheiros      INTEGER,
    JogosLidos     INTEGER,
    JogosGravados  INTEGER,
    Mensagem       TEXT
);

CREATE TABLE origem_calendario (
    IdAPI          INTEGER PRIMARY KEY,         -- identificador do jogo na API
    Jornada        INTEGER NOT NULL,
    DataHoraUTC    TEXT NOT NULL,               -- tal como veio da API (hora UTC)
    EquipaCasaAPI  TEXT NOT NULL,               -- nomes da API (ex.: Sport Lisboa e Benfica)
    EquipaForaAPI  TEXT NOT NULL,
    Estado         TEXT NOT NULL,
    GolosCasaAPI   INTEGER,                     -- vazio nos jogos por jogar
    GolosForaAPI   INTEGER
);

CREATE TABLE calendario (
    JogoID      TEXT PRIMARY KEY,               -- igual ao da tabela jogos (ex.: 2026-27_Benfica_Porto)
    Epoca       TEXT NOT NULL REFERENCES epocas (Epoca),
    Jornada     INTEGER NOT NULL CHECK (Jornada BETWEEN 1 AND 34),
    Data        TEXT NOT NULL,                  -- hora de Lisboa
    Hora        TEXT NOT NULL,
    EquipaCasa  TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora  TEXT NOT NULL REFERENCES equipas (Equipa),
    Estado      TEXT NOT NULL CHECK (Estado IN ('SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED', 'FINISHED',
                                                'POSTPONED', 'SUSPENDED', 'CANCELLED', 'AWARDED')),
    IdAPI       INTEGER NOT NULL UNIQUE REFERENCES origem_calendario (IdAPI)
);