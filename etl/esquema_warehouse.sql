-- =====================================================================
--  ESQUEMA DO DATA WAREHOUSE (PostgreSQL, schema gold) PARA O POWER BI
-- =====================================================================
--  Esquema em estrela: as dimensões descrevem (equipa, jornada, jogo),
--  os factos medem (probabilidades, acertos, pontos).
--  As tabelas são apagadas e criadas de novo em cada carregamento,
--  tudo numa só transação (ver warehouse.carregar): o Power BI vê
--  sempre a versão antiga completa ou a nova completa, nunca metade.
--
--  Os nomes das colunas vão entre aspas para manterem as maiúsculas
--  (ProbCasa e não probcasa) e aparecerem assim no Power BI.
-- =====================================================================

DROP TABLE IF EXISTS gold."fPrevisoes", gold."fAvaliacao_oficial", gold."fSimulacao",
                     gold."fPosicoes", gold."fClassificacao_jornada", gold."fHistorico",
                     gold."dJogo", gold."dJornada", gold."dEquipa", gold."fAtualizacao",
                     gold."dFase", gold."dModelo", gold."fAvaliacao_modelos", gold."fEpocas_equipa",
                     gold."fEquipa_jogo", gold."dJogador", gold."fJogador_epoca",
                     gold."fAvaliacao_epocas", gold."fCalibracao", gold."fEstatisticas_jogo", gold."fJogador_jogo";

-- ---------------------------------------------------------------------
--  DIMENSÕES
-- ---------------------------------------------------------------------

-- Uma linha por equipa da época atual
CREATE TABLE gold."dEquipa" (
    "Equipa"            TEXT PRIMARY KEY,
    "NomeApresentacao"  TEXT NOT NULL,
    "EmblemaURL"        TEXT
);

-- Uma linha por jornada (0 = início da época, antes do primeiro jogo)
CREATE TABLE gold."dJornada" (
    "Jornada"     SMALLINT PRIMARY KEY CHECK ("Jornada" BETWEEN 0 AND 34),
    "NomeCurto"   TEXT NOT NULL,          -- 'Início', 'J1', ..., 'J34' (ordenar pela coluna Jornada)
    "DataInicio"  DATE NOT NULL,           -- dia do primeiro jogo da jornada
    "Rotulo"      TEXT NOT NULL,          -- como o NomeCurto, mas 'Próxima' na próxima jornada (para o segmentador)
    "Estado"      TEXT NOT NULL CHECK ("Estado" IN ('Início', 'Jogada', 'Próxima', 'Futura')),
    "RotuloClassificacao"  TEXT NOT NULL,          -- como o Rotulo, mas 'Classificação' na próxima jornada (para o segmentador)
    "TemClassificacao"      SMALLINT NOT NULL CHECK ("TemClassificacao" IN (0, 1))   -- 1 = já tem classificação, 0 = ainda não
);

-- Uma linha por jogo da época atual. Leva os nomes e emblemas das duas equipas
-- (desnormalizada, como é habitual nas dimensões de um esquema em estrela)
CREATE TABLE gold."dJogo" (
    "JogoID"          TEXT PRIMARY KEY,
    "Jornada"         SMALLINT NOT NULL REFERENCES gold."dJornada" ("Jornada"),
    "Data"            DATE NOT NULL,
    "Hora"            TIME NOT NULL,
    "EquipaCasa"      TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "EquipaFora"      TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "NomeCasa"        TEXT NOT NULL,
    "NomeFora"        TEXT NOT NULL,
    "EmblemaCasa"     TEXT,
    "EmblemaFora"     TEXT,
    "Estado"          TEXT NOT NULL,
    "Tipo"            TEXT NOT NULL CHECK ("Tipo" IN ('Jogado', 'À espera de dados', 'Adiado', 'Remarcado', 'Próxima jornada', 'Provisória')),
    "GolosCasa"       SMALLINT,           -- vazio nos jogos por jogar
    "GolosFora"       SMALLINT,
    "Resultado"       TEXT CHECK ("Resultado" IN ('H', 'D', 'A')),
    "FonteResultado"  TEXT CHECK ("FonteResultado" IN ('CSV', 'API')),
    "OrdemJornada"    SMALLINT NOT NULL   -- 1, 2, 3, ... dentro da jornada (para ordenar no Power BI)
);

-- ---------------------------------------------------------------------
--  FACTOS
-- ---------------------------------------------------------------------

-- Previsão de hoje de cada jogo (modelo final, cada modelo e as odds)
CREATE TABLE gold."fPrevisoes" (
    "JogoID"                TEXT PRIMARY KEY REFERENCES gold."dJogo" ("JogoID"),
    "ProbCasa"              NUMERIC(5, 4) NOT NULL,
    "ProbEmpate"            NUMERIC(5, 4) NOT NULL,
    "ProbFora"              NUMERIC(5, 4) NOT NULL,
    "Previsto"              TEXT NOT NULL CHECK ("Previsto" IN ('H', 'D', 'A')),
    "Acerto"                SMALLINT,     -- 1 / 0; vazio nos jogos por jogar
    "LogLoss"               NUMERIC(7, 4),
    "RPS"                   NUMERIC(5, 4),
    "ProbCasaOrdinal"       NUMERIC(5, 4) NOT NULL,
    "ProbEmpateOrdinal"     NUMERIC(5, 4) NOT NULL,
    "ProbForaOrdinal"       NUMERIC(5, 4) NOT NULL,
    "ProbCasaDixonColes"    NUMERIC(5, 4) NOT NULL,
    "ProbEmpateDixonColes"  NUMERIC(5, 4) NOT NULL,
    "ProbForaDixonColes"    NUMERIC(5, 4) NOT NULL,
    "ProbCasaBoosting"      NUMERIC(5, 4) NOT NULL,
    "ProbEmpateBoosting"    NUMERIC(5, 4) NOT NULL,
    "ProbForaBoosting"      NUMERIC(5, 4) NOT NULL,
    "ProbOddsCasa"          NUMERIC(5, 4),   -- só nos jogos que já têm odds
    "ProbOddsEmpate"        NUMERIC(5, 4),
    "ProbOddsFora"          NUMERIC(5, 4),
    "ProbOddsFechoCasa"     NUMERIC(5, 4),
    "ProbOddsFechoEmpate"   NUMERIC(5, 4),
    "ProbOddsFechoFora"     NUMERIC(5, 4)
);

-- Previsões oficiais (congeladas no início da jornada) desde INICIO_PREVISOES_REAIS
CREATE TABLE gold."fAvaliacao_oficial" (
    "JogoID"          TEXT PRIMARY KEY REFERENCES gold."dJogo" ("JogoID"),
    "ProbCasa"        NUMERIC(5, 4) NOT NULL,
    "ProbEmpate"      NUMERIC(5, 4) NOT NULL,
    "ProbFora"        NUMERIC(5, 4) NOT NULL,
    "Previsto"        TEXT NOT NULL CHECK ("Previsto" IN ('H', 'D', 'A')),
    "Acerto"          SMALLINT,
    "LogLoss"         NUMERIC(7, 4),
    "RPS"             NUMERIC(5, 4),
    "ProbOddsCasa"    NUMERIC(5, 4),
    "ProbOddsEmpate"  NUMERIC(5, 4),
    "ProbOddsFora"    NUMERIC(5, 4)
);

-- Estatísticas de cada jogo já jogado que está no CSV (os que só vieram da API ainda não as têm)
CREATE TABLE gold."fEstatisticas_jogo" (
    "JogoID"              TEXT PRIMARY KEY REFERENCES gold."dJogo" ("JogoID"),
    "GolosCasaIntervalo"  SMALLINT,
    "GolosForaIntervalo"  SMALLINT,
    "RematesCasa"         SMALLINT,
    "RematesFora"         SMALLINT,
    "RematesBalizaCasa"   SMALLINT,
    "RematesBalizaFora"   SMALLINT,
    "CantosCasa"          SMALLINT,
    "CantosFora"          SMALLINT,
    "FaltasCasa"          SMALLINT,
    "FaltasFora"          SMALLINT,
    "AmarelosCasa"        SMALLINT,
    "AmarelosFora"        SMALLINT,
    "VermelhosCasa"       SMALLINT,
    "VermelhosFora"       SMALLINT
);

-- Classificação das épocas anteriores por equipa
CREATE TABLE gold."fEpocas_equipa" (
    "Epoca"              TEXT NOT NULL,
    "Equipa"             TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Posicao"            SMALLINT NOT NULL,
    "Jogos"              SMALLINT NOT NULL,
    "Vitorias"           SMALLINT NOT NULL,
    "Empates"            SMALLINT NOT NULL,
    "Derrotas"           SMALLINT NOT NULL,
    "GolosMarcados"      SMALLINT NOT NULL,
    "GolosSofridos"      SMALLINT NOT NULL,
    "DiferencaGolos"     SMALLINT NOT NULL,
    "Pontos"             SMALLINT NOT NULL,
    PRIMARY KEY ("Epoca", "Equipa")
);

-- Classificação de hoje e resultado das 10 000 simulações, por equipa
CREATE TABLE gold."fSimulacao" (
    "Equipa"              TEXT PRIMARY KEY REFERENCES gold."dEquipa" ("Equipa"),
    "Posicao"             SMALLINT NOT NULL,
    "Jogos"               SMALLINT NOT NULL,
    "Vitorias"            SMALLINT NOT NULL,
    "Empates"             SMALLINT NOT NULL,
    "Derrotas"            SMALLINT NOT NULL,
    "GolosMarcados"       SMALLINT NOT NULL,
    "GolosSofridos"       SMALLINT NOT NULL,
    "DiferencaGolos"      SMALLINT NOT NULL,
    "Pontos"              SMALLINT NOT NULL,
    "PontosEsperados"     NUMERIC(5, 2) NOT NULL,
    "PontosP10"           NUMERIC(5, 1) NOT NULL,
    "PontosP90"           NUMERIC(5, 1) NOT NULL,
    "PosicaoMedia"        NUMERIC(4, 2) NOT NULL,
    "ProbCampeao"         NUMERIC(5, 4) NOT NULL,
    "ProbTop3"            NUMERIC(5, 4) NOT NULL,
    "ProbEuropa"          NUMERIC(5, 4) NOT NULL,
    "ProbPlayoffDescida"  NUMERIC(5, 4) NOT NULL,
    "ProbDescida"         NUMERIC(5, 4) NOT NULL
);

-- Probabilidade de cada equipa acabar em cada posição (para o mapa de calor)
CREATE TABLE gold."fPosicoes" (
    "Equipa"         TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Posicao"        SMALLINT NOT NULL CHECK ("Posicao" BETWEEN 1 AND 18),
    "Probabilidade"  NUMERIC(5, 4) NOT NULL,
    PRIMARY KEY ("Equipa", "Posicao")
);

-- Classificação depois de cada jornada
CREATE TABLE gold."fClassificacao_jornada" (
    "Jornada"         SMALLINT NOT NULL REFERENCES gold."dJornada" ("Jornada"),
    "Equipa"          TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Posicao"         SMALLINT NOT NULL,
    "Jogos"           SMALLINT NOT NULL,
    "Vitorias"        SMALLINT NOT NULL,
    "Empates"         SMALLINT NOT NULL,
    "Derrotas"        SMALLINT NOT NULL,
    "GolosMarcados"   SMALLINT NOT NULL,
    "GolosSofridos"   SMALLINT NOT NULL,
    "DiferencaGolos"  SMALLINT NOT NULL,
    "Pontos"          SMALLINT NOT NULL,
    "VariacaoPosicao" SMALLINT,   -- diferença para a jornada anterior
    PRIMARY KEY ("Jornada", "Equipa")
);

-- Como estava a simulação depois de cada jornada (do historico.db)
CREATE TABLE gold."fHistorico" (
    "Jornada"             SMALLINT NOT NULL REFERENCES gold."dJornada" ("Jornada"),
    "Equipa"              TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "PontosEsperados"     NUMERIC(5, 2) NOT NULL,
    "PontosP10"           NUMERIC(5, 1) NOT NULL,
    "PontosP90"           NUMERIC(5, 1) NOT NULL,
    "PosicaoMedia"        NUMERIC(4, 2) NOT NULL,
    "ProbCampeao"         NUMERIC(5, 4) NOT NULL,
    "ProbTop3"            NUMERIC(5, 4) NOT NULL,
    "ProbEuropa"          NUMERIC(5, 4) NOT NULL,
    "ProbPlayoffDescida"  NUMERIC(5, 4) NOT NULL,
    "ProbDescida"         NUMERIC(5, 4) NOT NULL,
    PRIMARY KEY ("Jornada", "Equipa")
);

CREATE TABLE gold."fAtualizacao" (
    "CarregadoEm"                 TIMESTAMP NOT NULL,
    "CalendarioDescarregadoEm"    TIMESTAMP NOT NULL,
    "UltimoJogoTerminado"         DATE,
    "UltimoJogoCSV"               DATE NOT NULL,
    PRIMARY KEY ("CarregadoEm")
);

-- As duas fases da avaliação, pela ordem certa (sem a Ordem, o Power BI punha o Teste primeiro)
CREATE TABLE gold."dFase" (
    "Fase"    TEXT PRIMARY KEY CHECK ("Fase" IN ('Validação', 'Teste')),
    "Ordem"   SMALLINT NOT NULL,
    "Epocas"  TEXT NOT NULL               -- '21-22 a 24-25' ou '25-26'
);

-- Os 7 modelos comparados, pela ordem do relatório
CREATE TABLE gold."dModelo" (
    "Modelo"  TEXT PRIMARY KEY,
    "Grupo"   TEXT NOT NULL CHECK ("Grupo" IN ('Modelo', 'Casas de apostas', 'Referência')),
    "Ordem"   SMALLINT NOT NULL
);

-- Uma linha por fase e modelo. DifReferencia = log loss do modelo menos o das odds de
-- abertura (negativo = melhor do que as casas);
CREATE TABLE gold."fAvaliacao_modelos" (
    "Fase"           TEXT NOT NULL REFERENCES gold."dFase" ("Fase"),
    "Modelo"         TEXT NOT NULL REFERENCES gold."dModelo" ("Modelo"),
    "Jogos"          SMALLINT NOT NULL,
    "Acerto"         NUMERIC(5, 4) NOT NULL,
    "LogLoss"        NUMERIC(5, 4) NOT NULL,
    "RPS"            NUMERIC(5, 4) NOT NULL,
    "ECE"            NUMERIC(5, 4),
    "DifReferencia"  NUMERIC(5, 4) NOT NULL,
    "DifInferior"    NUMERIC(5, 4) NOT NULL,
    "DifSuperior"    NUMERIC(5, 4) NOT NULL,
    PRIMARY KEY ("Fase", "Modelo")
);

-- Uma linha por fase, época e modelo (linha do tempo)
CREATE TABLE gold."fAvaliacao_epocas" (
    "Fase"     TEXT NOT NULL REFERENCES gold."dFase" ("Fase"),
    "Epoca"    TEXT NOT NULL,
    "Modelo"   TEXT NOT NULL REFERENCES gold."dModelo" ("Modelo"),
    "Jogos"    SMALLINT NOT NULL,
    "Acerto"   NUMERIC(5, 4) NOT NULL,
    "LogLoss"  NUMERIC(5, 4) NOT NULL,
    "RPS"      NUMERIC(5, 4) NOT NULL,
    PRIMARY KEY ("Fase", "Epoca", "Modelo")
);

-- Calibração: uma linha por fase, modelo, resultado e faixa de probabilidade (só faixas com 20+ jogos)
CREATE TABLE gold."fCalibracao" (
    "Fase"           TEXT NOT NULL REFERENCES gold."dFase" ("Fase"),
    "Modelo"         TEXT NOT NULL REFERENCES gold."dModelo" ("Modelo"),
    "Resultado"      TEXT NOT NULL CHECK ("Resultado" IN ('Casa', 'Empate', 'Fora')),
    "Faixa"          SMALLINT NOT NULL,
    "RotuloFaixa"    TEXT NOT NULL,
    "ProbMedia"      NUMERIC(5, 4) NOT NULL,   -- o que o modelo disse, em média
    "FreqObservada"  NUMERIC(5, 4) NOT NULL,   -- o que aconteceu
    "Jogos"          SMALLINT NOT NULL,
    PRIMARY KEY ("Fase", "Modelo", "Resultado", "Faixa")
);

-- Posse e passes de cada equipa em cada jogo (fichas da ESPN), com os golos para a eficiência
CREATE TABLE gold."fEquipa_jogo" (
    "JogoID"              TEXT NOT NULL REFERENCES gold."dJogo" ("JogoID"),
    "Equipa"              TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Golos"               SMALLINT NOT NULL,
    "PosseBola"           NUMERIC(4, 1),
    "PassesCertos"        SMALLINT,
    "Passes"              SMALLINT,
    "CruzamentosCertos"   SMALLINT,
    "Cruzamentos"         SMALLINT,
    "PassesLongosCertos"  SMALLINT,
    "PassesLongos"        SMALLINT,
    "Remates"             SMALLINT,
    "RematesBaliza"       SMALLINT,
    PRIMARY KEY ("JogoID", "Equipa")
);

-- Um jogador por linha (o nome é único: é por ele que o Power BI passa o jogador à descrição)
CREATE TABLE gold."dJogador" (
    "JogadorID"  TEXT PRIMARY KEY,
    "Nome"       TEXT NOT NULL UNIQUE,
    "Linha"      TEXT NOT NULL CHECK ("Linha" IN ('GR', 'DEF', 'MED', 'AV', 'S/P'))
);

-- A época de cada jogador em cada equipa: totais, função, impacto e lugar no gráfico do plantel
CREATE TABLE gold."fJogador_epoca" (
    "JogadorID"           TEXT NOT NULL REFERENCES gold."dJogador" ("JogadorID"),
    "Equipa"              TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Convocatorias"       SMALLINT NOT NULL,
    "Jogos"               SMALLINT NOT NULL,
    "Titularidades"       SMALLINT NOT NULL,
    "Minutos"             SMALLINT NOT NULL,
    "GolosProEmCampo"     SMALLINT NOT NULL,
    "GolosContraEmCampo"  SMALLINT NOT NULL,
    "JogosSemSofrer"      SMALLINT NOT NULL,
    "Golos"               SMALLINT NOT NULL,
    "Assistencias"        SMALLINT NOT NULL,
    "Autogolos"           SMALLINT NOT NULL,
    "Remates"             SMALLINT NOT NULL,
    "RematesBaliza"       SMALLINT NOT NULL,
    "FaltasCometidas"     SMALLINT NOT NULL,
    "FaltasSofridas"      SMALLINT NOT NULL,
    "ForasDeJogo"         SMALLINT NOT NULL,
    "Amarelos"            SMALLINT NOT NULL,
    "Vermelhos"           SMALLINT NOT NULL,
    "Defesas"             SMALLINT NOT NULL,
    "RematesEnfrentados"  SMALLINT NOT NULL,
    "GolosSofridos"       SMALLINT NOT NULL,
    "PercMinutos"         NUMERIC(5, 4) NOT NULL,   -- parte dos minutos da equipa que jogou (0 a 1)
    "Funcao"              TEXT NOT NULL CHECK ("Funcao" IN ('Titular habitual', 'Rotação', 'Pouco utilizado', 'Sem minutos')),
    "SaldoComEle90"       NUMERIC(6, 4),            -- golos a favor menos contra por 90 min com ele em campo
    "SaldoSemEle90"       NUMERIC(6, 4),            -- o mesmo sem ele (vazio com menos de 450 min)
    "Impacto90"           NUMERIC(6, 4),            -- com ele menos sem ele
    "PlantelX"            SMALLINT NOT NULL,        -- lugar da bolinha na linha (0 ao centro)
    "PlantelY"            SMALLINT NOT NULL,        -- a linha (5 avançados ... 1 sem posição)
    PRIMARY KEY ("JogadorID", "Equipa")
);

-- Um jogador por jogo (fichas da ESPN): o campo da página da Equipa, jornada a jornada
CREATE TABLE gold."fJogador_jogo" (
    "JogoID"        TEXT NOT NULL REFERENCES gold."dJogo" ("JogoID"),
    "JogadorID"     TEXT NOT NULL REFERENCES gold."dJogador" ("JogadorID"),
    "Equipa"        TEXT NOT NULL REFERENCES gold."dEquipa" ("Equipa"),
    "Rotulo"        TEXT NOT NULL,          -- nome curto e o que fez no jogo (ex.: 'T. Araújo' e os golos)
    "Formacao"      TEXT,                   -- '4-2-3-1', ...
    "PosicaoCurta"  TEXT,                   -- 'CD-L', 'AM', ... (a da ESPN)
    "Titular"       SMALLINT NOT NULL,
    "Entrou"        NUMERIC(5, 1),          -- minuto (0 nos titulares; vazio se não jogou)
    "Saiu"          NUMERIC(5, 1),
    "Minutos"       NUMERIC(5, 1) NOT NULL,
    "Substituiu"    TEXT,                   -- JogadorID de quem saiu quando ele entrou
    "CampoX"        SMALLINT,               -- lugar no campo, de 0 a 100 (só titulares)
    "CampoY"        SMALLINT,
    "Golos"         SMALLINT,
    "Assistencias"  SMALLINT,
    "Amarelos"      SMALLINT,
    "Vermelhos"     SMALLINT,
    PRIMARY KEY ("JogoID", "JogadorID")
);