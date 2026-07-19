-- Continuo schema. Idempotent: safe to run repeatedly (docker init + ingest script both apply it).

CREATE TABLE IF NOT EXISTS top_movers (
    id              serial PRIMARY KEY,
    ticker          text        NOT NULL,
    date            date        NOT NULL,
    direction       text        NOT NULL CHECK (direction IN ('gainer', 'loser')),
    pct_change      numeric,
    price           numeric,
    volume          bigint,
    avg_volume_20d  numeric,          -- relative-volume feature; NULL until OHLCV backfill (week 2)
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- One row per ticker per trading day → re-running ingestion is idempotent.
    UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_top_movers_date ON top_movers (date);
