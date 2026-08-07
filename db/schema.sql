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

-- Daily OHLCV cache (backfilled from yfinance) — source for engineered features + labels.
CREATE TABLE IF NOT EXISTS ohlcv (
    ticker  text   NOT NULL,
    date    date   NOT NULL,
    open    numeric,
    high    numeric,
    low     numeric,
    close   numeric,
    volume  bigint,
    PRIMARY KEY (ticker, date)
);

-- Engineered v1 feature set + next-day label, one row per mover (ticker, mover_date).
-- Features use only info available at the mover-day close; label uses the next day (no leakage).
CREATE TABLE IF NOT EXISTS features (
    ticker       text        NOT NULL,
    mover_date   date        NOT NULL,
    direction    text        NOT NULL,
    gap_pct      numeric,          -- (mover-day open - prior close) / prior close
    pct_change   numeric,          -- mover-day % change (from top_movers)
    rel_volume   numeric,          -- mover-day volume / 20d avg volume
    trend_5d     numeric,          -- % return over the 5 trading days before the mover day
    day_of_week  smallint,         -- 0=Mon … 4=Fri
    target_date  date,             -- next trading day
    label        smallint,         -- 1 if next-day close > mover-day close, else 0
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, mover_date)
);

CREATE INDEX IF NOT EXISTS idx_features_mover_date ON features (mover_date);
