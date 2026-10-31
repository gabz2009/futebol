-- =====================================================================
--  ESQUEMA DAS TABELAS DA FASE 7 (PREVISÕES DA ÉPOCA ATUAL)
-- =====================================================================
--  Como na fase 2: as tabelas são criadas com o sufixo _nova e só no
--  fim trocam as antigas (ver guardar.substituir_tabelas).
-- =====================================================================

DROP TABLE IF EXISTS previsoes_nova;
DROP TABLE IF EXISTS qa_previsoes_nova;

CREATE TABLE previsoes_nova (
    JogoID                TEXT PRIMARY KEY REFERENCES calendario (JogoID),
    Epoca                 TEXT NOT NULL,
    Jornada               INTEGER NOT NULL,
    Data                  TEXT NOT NULL,      -- data real do calendário (hora de Lisboa)
    Hora                  TEXT NOT NULL,
    EquipaCasa            TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora            TEXT NOT NULL REFERENCES equipas (Equipa),
    Estado                TEXT NOT NULL,      -- estado na API (FINISHED, TIMED, POSTPONED...)
    Jogado                INTEGER NOT NULL CHECK (Jogado IN (0, 1)),   -- 1 = já com dados no CSV
    Tipo                  TEXT NOT NULL CHECK (Tipo IN ('Jogado','À espera de dados', 'Próxima jornada', 'Provisória')),
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

CREATE TABLE qa_previsoes_nova (
    Controlo   TEXT PRIMARY KEY,
    Descricao  TEXT NOT NULL,
    Esperado   TEXT,
    Obtido     TEXT,
    Estado     TEXT NOT NULL,
    Critico    INTEGER NOT NULL,
    Detalhe    TEXT
);