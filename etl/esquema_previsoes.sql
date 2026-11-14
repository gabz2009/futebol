-- =====================================================================
--  ESQUEMA DAS TABELAS DA FASE 7 (PREVISÕES DA ÉPOCA ATUAL)
-- =====================================================================
--  Como na fase 2: as tabelas são criadas com o sufixo _nova e só no
--  fim trocam as antigas (ver guardar.substituir_tabelas).
-- =====================================================================

DROP TABLE IF EXISTS previsoes_nova;
DROP TABLE IF EXISTS qa_previsoes_nova;
DROP TABLE IF EXISTS simulacao_epoca_nova;
DROP TABLE IF EXISTS simulacao_posicoes_nova;
DROP TABLE IF EXISTS classificacao_jornada_nova;
DROP TABLE IF EXISTS avaliacao_oficial_nova;


-- Uma linha por equipa: classificação atual e o resultado das simulações
CREATE TABLE simulacao_epoca_nova (
    Posicao             INTEGER NOT NULL,     -- posição atual
    Equipa              TEXT PRIMARY KEY REFERENCES equipas (Equipa),
    Jogos               INTEGER NOT NULL,
    Vitorias            INTEGER NOT NULL,
    Empates             INTEGER NOT NULL,
    Derrotas            INTEGER NOT NULL,
    GolosMarcados       INTEGER NOT NULL,
    GolosSofridos       INTEGER NOT NULL,
    Pontos              INTEGER NOT NULL,
    DiferencaGolos      INTEGER NOT NULL,
    PontosEsperados     REAL NOT NULL,        -- média dos pontos finais nas simulações
    PontosP10           REAL NOT NULL,        -- 10% das simulações acabam abaixo disto
    PontosP90           REAL NOT NULL,        -- 10% das simulações acabam acima disto
    PosicaoMedia        REAL NOT NULL,
    ProbCampeao         REAL NOT NULL CHECK (ProbCampeao BETWEEN 0 AND 1),
    ProbTop3            REAL NOT NULL CHECK (ProbTop3 BETWEEN 0 AND 1),
    ProbEuropa          REAL NOT NULL CHECK (ProbEuropa BETWEEN 0 AND 1),
    ProbPlayoffDescida  REAL NOT NULL CHECK (ProbPlayoffDescida BETWEEN 0 AND 1),
    ProbDescida         REAL NOT NULL CHECK (ProbDescida BETWEEN 0 AND 1),
    Simulacoes          INTEGER NOT NULL
);

-- Probabilidade de cada equipa acabar em cada posição (para um mapa de calor no Power BI)
CREATE TABLE simulacao_posicoes_nova (
    Equipa         TEXT NOT NULL REFERENCES equipas (Equipa),
    Posicao        INTEGER NOT NULL CHECK (Posicao BETWEEN 1 AND 18),
    Probabilidade  REAL NOT NULL CHECK (Probabilidade BETWEEN 0 AND 1),
    PRIMARY KEY (Equipa, Posicao)
);

CREATE TABLE previsoes_nova (
    JogoID                TEXT PRIMARY KEY REFERENCES calendario (JogoID),
    Epoca                 TEXT NOT NULL,
    Jornada               INTEGER NOT NULL,
    Data                  TEXT NOT NULL,      -- data real do calendário (hora de Lisboa)
    Hora                  TEXT NOT NULL,
    EquipaCasa            TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora            TEXT NOT NULL REFERENCES equipas (Equipa),
    Estado                TEXT NOT NULL,      -- estado na API (FINISHED, TIMED, POSTPONED...)
    Jogado                INTEGER NOT NULL CHECK (Jogado IN (0, 1)),   -- 1 = já tem resultado (do CSV ou da API)
    FonteResultado        TEXT CHECK (FonteResultado IN ('CSV', 'API')),   -- API = ainda sem estatísticas no CSV
    GolosCasa             INTEGER,            -- vazio nos jogos por jogar
    GolosFora             INTEGER,
    Tipo                  TEXT NOT NULL CHECK (Tipo IN ('Jogado', 'À espera de dados', 'Adiado', 'Remarcado', 'Próxima jornada', 'Provisória')),
    Resultado             TEXT CHECK (Resultado IN ('H', 'D', 'A')),   -- vazio nos jogos por jogar
    -- Modelo final (média geométrica dos três)
    ProbCasa              REAL NOT NULL CHECK (ProbCasa BETWEEN 0 AND 1),
    ProbEmpate            REAL NOT NULL CHECK (ProbEmpate BETWEEN 0 AND 1),
    ProbFora              REAL NOT NULL CHECK (ProbFora BETWEEN 0 AND 1),
    Previsto              TEXT NOT NULL CHECK (Previsto IN ('H', 'D', 'A')),   -- resultado mais provável
    Acerto                REAL,               -- só nos jogos jogados
    LogLoss               REAL,
    RPS                   REAL,
    -- Cada modelo do modelo final
    ProbCasaOrdinal       REAL NOT NULL,
    ProbEmpateOrdinal     REAL NOT NULL,
    ProbForaOrdinal       REAL NOT NULL,
    ProbCasaDixonColes    REAL NOT NULL,
    ProbEmpateDixonColes  REAL NOT NULL,
    ProbForaDixonColes    REAL NOT NULL,
    ProbCasaBoosting      REAL NOT NULL,
    ProbEmpateBoosting    REAL NOT NULL,
    ProbForaBoosting      REAL NOT NULL,
    -- Odds (só nos jogos que já têm odds no CSV)
    ProbOddsCasa          REAL,               -- odds pré-jogo
    ProbOddsEmpate        REAL,
    ProbOddsFora          REAL,
    ProbOddsFechoCasa     REAL,               -- odds de fecho
    ProbOddsFechoEmpate   REAL,
    ProbOddsFechoFora     REAL
);

-- Classificação depois de cada jornada (só jogos terminados dessa jornada e das anteriores)
CREATE TABLE classificacao_jornada_nova (
    Posicao         INTEGER NOT NULL,
    Equipa          TEXT NOT NULL REFERENCES equipas (Equipa),
    Jogos           INTEGER NOT NULL,
    Vitorias        INTEGER NOT NULL,
    Empates         INTEGER NOT NULL,
    Derrotas        INTEGER NOT NULL,
    GolosMarcados   INTEGER NOT NULL,
    GolosSofridos   INTEGER NOT NULL,
    Pontos          INTEGER NOT NULL,
    DiferencaGolos  INTEGER NOT NULL,
    Jornada         INTEGER NOT NULL CHECK (Jornada BETWEEN 1 AND 34),
    PRIMARY KEY (Jornada, Equipa)
);

CREATE TABLE avaliacao_oficial_nova (
        JogoID          TEXT PRIMARY KEY REFERENCES calendario (JogoID),
    Epoca           TEXT NOT NULL,
    Jornada         INTEGER NOT NULL CHECK (Jornada BETWEEN 1 AND 34),
    DataCorte       TEXT NOT NULL,      -- previsão feita só com os jogos antes desta data
    Data            TEXT NOT NULL,
    Hora            TEXT NOT NULL,
    EquipaCasa      TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora      TEXT NOT NULL REFERENCES equipas (Equipa),
    ProbCasa        REAL NOT NULL CHECK (ProbCasa BETWEEN 0 AND 1),
    ProbEmpate      REAL NOT NULL CHECK (ProbEmpate BETWEEN 0 AND 1),
    ProbFora        REAL NOT NULL CHECK (ProbFora BETWEEN 0 AND 1),
    Previsto        TEXT NOT NULL CHECK (Previsto IN ('H', 'D', 'A')),
    Resultado       TEXT CHECK (Resultado IN ('H', 'D', 'A')),          -- vazio nos jogos por jogar
    FonteResultado  TEXT CHECK (FonteResultado IN ('CSV', 'API')),
    Acerto          REAL,
    LogLoss         REAL,
    RPS             REAL,
    ProbOddsCasa    REAL,               -- odds pré-jogo (só quando o jogo já está no CSV)
    ProbOddsEmpate  REAL,
    ProbOddsFora    REAL
);

CREATE TABLE qa_previsoes_nova (
    Controlo   TEXT PRIMARY KEY,
    Descricao  TEXT NOT NULL,
    Esperado   TEXT,
    Obtido     TEXT,
    Estado     TEXT NOT NULL,
    Critico    INTEGER NOT NULL,
    Detalhe    TEXT
);