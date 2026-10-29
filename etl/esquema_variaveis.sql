-- =====================================================================
--  ESQUEMA DAS TABELAS DA FASE 2 (VARIÁVEIS)
-- =====================================================================
--  As tabelas são criadas com o sufixo _nova. O Python enche-as e só
--  no fim troca as antigas pelas novas (ver guardar.substituir_tabelas).
--
--  ATENÇÃO: os nomes com "Ult5" dependem de JANELA_FORMA = 5. Se
--  mudares a janela, tens de mudar os nomes aqui também (o script dá
--  erro a avisar que a coluna não existe).
-- =====================================================================

DROP TABLE IF EXISTS variaveis_nova;
DROP TABLE IF EXISTS qa_variaveis_nova;

CREATE TABLE variaveis_nova (
    -- Identificação do jogo
    JogoID                         TEXT PRIMARY KEY REFERENCES jogos (JogoID),
    Epoca                          TEXT NOT NULL REFERENCES epocas (Epoca),
    Data                           TEXT NOT NULL,
    EquipaCasa                     TEXT NOT NULL REFERENCES equipas (Equipa),
    EquipaFora                     TEXT NOT NULL REFERENCES equipas (Equipa),
    EpocaCOVID                     INTEGER NOT NULL,

    -- Equipa da casa (médias dos jogos anteriores)
    CasaPontosUlt5                 REAL,       -- vazias só na época de aquecimento
    CasaGolosMarcadosUlt5          REAL,
    CasaGolosSofridosUlt5          REAL,
    CasaRematesBalizaUlt5          REAL,
    CasaRematesBalizaSofridosUlt5  REAL,
    CasaPontosLocal                REAL,
    CasaDiasDescanso               INTEGER NOT NULL,
    CasaJogosNaEpoca               INTEGER NOT NULL,
    CasaPromovida                  INTEGER NOT NULL,

    -- Equipa de fora
    ForaPontosUlt5                 REAL,
    ForaGolosMarcadosUlt5          REAL,
    ForaGolosSofridosUlt5          REAL,
    ForaRematesBalizaUlt5          REAL,
    ForaRematesBalizaSofridosUlt5  REAL,
    ForaPontosLocal                REAL,
    ForaDiasDescanso               INTEGER NOT NULL,
    ForaJogosNaEpoca               INTEGER NOT NULL,
    ForaPromovida                  INTEGER NOT NULL,

    -- Elo antes do jogo
    EloCasa                        REAL NOT NULL,
    EloFora                        REAL NOT NULL,

    -- Diferenças casa - fora (podem ser negativas)
    DifPontosUlt5                  REAL,
    DifGolosMarcadosUlt5           REAL,
    DifGolosSofridosUlt5           REAL,
    DifRematesBalizaUlt5           REAL,
    DifRematesBalizaSofridosUlt5   REAL,
    DifPontosLocal                 REAL,
    DifDiasDescanso                INTEGER NOT NULL,
    DifElo                         REAL NOT NULL,
    EquilibrioElo                  REAL NOT NULL CHECK (EquilibrioElo >= 0),

    -- Pi-ratings antes do jogo
    PiCasa                         REAL NOT NULL,
    PiFora                         REAL NOT NULL,
    PiDifEsperada                  REAL NOT NULL,
    EquilibrioPi                   REAL NOT NULL CHECK (EquilibrioPi >= 0),

    GapFalhadosCasa                REAL NOT NULL CHECK (GapFalhadosCasa >= 0),
    GapFalhadosFora                REAL NOT NULL CHECK (GapFalhadosFora >= 0),
    GapFalhadosDif                 REAL NOT NULL,
    GapBalizaCasa                  REAL NOT NULL CHECK (GapBalizaCasa >= 0),
    GapBalizaFora                  REAL NOT NULL CHECK (GapBalizaFora >= 0),
    GapBalizaDif                   REAL NOT NULL,
    GapCantosCasa                  REAL NOT NULL CHECK (GapCantosCasa >= 0),
    GapCantosFora                  REAL NOT NULL CHECK (GapCantosFora >= 0),
    GapCantosDif                   REAL NOT NULL,


    -- Probabilidades das odds (só para comparar, não entram no modelo)
    ProbOddsCasa                   REAL,
    ProbOddsEmpate                 REAL,
    ProbOddsFora                   REAL,
    ProbOddsFechoCasa              REAL,
    ProbOddsFechoEmpate            REAL,
    ProbOddsFechoFora              REAL,

    -- Uso da época e alvo
    Uso                            TEXT NOT NULL,
    Resultado                      TEXT CHECK (Resultado IN ('H', 'D', 'A'))   -- vazio nos jogos ainda por jogar
);

CREATE TABLE qa_variaveis_nova (
    Controlo   TEXT PRIMARY KEY,
    Descricao  TEXT NOT NULL,
    Esperado   TEXT,
    Obtido     TEXT,
    Estado     TEXT NOT NULL,
    Critico    INTEGER NOT NULL,
    Detalhe    TEXT
);