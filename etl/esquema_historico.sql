-- =====================================================================
--  ESQUEMA DA BASE DE DADOS DO HISTÓRICO (dados/historico.db)
-- =====================================================================
--  Esta base NÃO é recriada: as tabelas só são criadas se ainda não
--  existirem (IF NOT EXISTS) e as linhas vão sendo acrescentadas.
-- =====================================================================

-- Uma linha por época, jornada e equipa: como estava a simulação depois dessa jornada
-- (Jornada 0 = início da época, antes do primeiro jogo)
CREATE TABLE IF NOT EXISTS historico_simulacao (
    Epoca               TEXT NOT NULL,
    Jornada             INTEGER NOT NULL CHECK (Jornada BETWEEN 0 AND 34),
    DataCorte           TEXT NOT NULL,        -- só entram os jogos antes desta data
    Posicao             INTEGER NOT NULL,     -- posição nessa altura
    Equipa              TEXT NOT NULL,
    Jogos               INTEGER NOT NULL,
    Vitorias            INTEGER NOT NULL,
    Empates             INTEGER NOT NULL,
    Derrotas            INTEGER NOT NULL,
    GolosMarcados       INTEGER NOT NULL,
    GolosSofridos       INTEGER NOT NULL,
    Pontos              INTEGER NOT NULL,
    DiferencaGolos      INTEGER NOT NULL,
    PontosEsperados     REAL NOT NULL,
    PontosP10           REAL NOT NULL,
    PontosP90           REAL NOT NULL,
    PosicaoMedia        REAL NOT NULL,
    ProbCampeao         REAL NOT NULL CHECK (ProbCampeao BETWEEN 0 AND 1),
    ProbTop3            REAL NOT NULL CHECK (ProbTop3 BETWEEN 0 AND 1),
    ProbEuropa          REAL NOT NULL CHECK (ProbEuropa BETWEEN 0 AND 1),
    ProbPlayoffDescida  REAL NOT NULL CHECK (ProbPlayoffDescida BETWEEN 0 AND 1),
    ProbDescida         REAL NOT NULL CHECK (ProbDescida BETWEEN 0 AND 1),
    Simulacoes          INTEGER NOT NULL,
    PRIMARY KEY (Epoca, Jornada, Equipa)
);