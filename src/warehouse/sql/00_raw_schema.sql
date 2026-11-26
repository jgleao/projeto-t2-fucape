-- =============================================================================
-- CAMADA RAW (BRONZE): dados no formato original da API, um registro por
-- objeto atomico (uma review / um jogo). Idempotencia garantida pela chave
-- natural da fonte como PRIMARY KEY + upsert por hash do payload.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.steam_reviews (
    recommendationid   TEXT        PRIMARY KEY,           -- chave natural da Steam
    app_id             INTEGER     NOT NULL,
    payload            JSONB       NOT NULL,              -- objeto review original, sem alteracao
    payload_hash       TEXT        NOT NULL,              -- sha256 do payload (detecta mudanca)
    timestamp_created  BIGINT,
    timestamp_updated  BIGINT,
    first_ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(), -- muda so quando o payload muda
    last_run_id        TEXT
);
CREATE INDEX IF NOT EXISTS ix_raw_reviews_app_created ON raw.steam_reviews (app_id, timestamp_created);
CREATE INDEX IF NOT EXISTS ix_raw_reviews_ingested ON raw.steam_reviews (last_ingested_at);

CREATE TABLE IF NOT EXISTS raw.steam_app_details (
    app_id        INTEGER     PRIMARY KEY,
    payload       JSONB       NOT NULL,                   -- {"success": ..., "data": {...}} original
    payload_hash  TEXT        NOT NULL,
    success       BOOLEAN     NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_id   TEXT
);

-- Auditoria da ingestao: uma linha por (execucao do DAG, jogo, entidade).
-- Reexecutar a mesma tarefa sobrescreve a linha da mesma execucao.
CREATE TABLE IF NOT EXISTS raw.ingestion_log (
    run_id          TEXT        NOT NULL,
    app_id          INTEGER     NOT NULL,
    entidade        TEXT        NOT NULL,                 -- 'reviews' | 'detalhes'
    status          TEXT        NOT NULL,                 -- 'sucesso' | 'erro'
    paginas         INTEGER     NOT NULL DEFAULT 0,
    linhas_recebidas INTEGER    NOT NULL DEFAULT 0,
    linhas_inseridas INTEGER    NOT NULL DEFAULT 0,
    linhas_atualizadas INTEGER  NOT NULL DEFAULT 0,
    requisicoes     INTEGER     NOT NULL DEFAULT 0,
    retentativas    INTEGER     NOT NULL DEFAULT 0,
    respostas_429   INTEGER     NOT NULL DEFAULT 0,
    motivo_parada   TEXT,
    mensagem        TEXT,
    iniciado_em     TIMESTAMPTZ NOT NULL,
    finalizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, app_id, entidade)
);
