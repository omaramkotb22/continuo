# Continuo

Will today's top mover keep moving tomorrow? Continuo is a backend-first ML pipeline that ingests the daily stock-market "top movers," stores them in Postgres, and (later) engineers features, trains a next-day continuation classifier, and serves predictions over a REST API. It's a portfolio project focused on engineering discipline — pipeline shape, IaC, CI/CD, honest backtesting — not a trading bot.

See [CONTINUO.md](CONTINUO.md) for the full plan and task breakdown.

## Pipeline so far (Days 1–3, all local)

```
Alpha Vantage TOP_GAINERS_LOSERS
  → fetch_movers.py → data/raw/movers_<date>.json  (raw archive)
                    → Postgres top_movers            (idempotent upsert)
  → plot_movers.py → reports/movers_<date>.png       (chart)
  ↳ run_daily.sh via cron (01:30 daily, after US close)
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # paste your Alpha Vantage key into .env
docker compose up -d          # local Postgres on host port 5433
python fetch_movers.py        # save raw JSON + upsert into top_movers
python plot_movers.py         # render reports/movers_<date>.png
```

Free Alpha Vantage key: <https://www.alphavantage.co/support/#api-key>

## Daily automation

`run_daily.sh` brings up Postgres, ingests, and redraws the chart; it's idempotent
(re-running for the same trading day updates rows in place). A cron entry runs it
at 01:30 Asia/Dubai — just after the US market close:

```
30 1 * * * /path/to/continuo/run_daily.sh # continuo-daily-ingest
```

## Sample output

![Top movers chart](reports/movers_2026-07-17.png)

## Data model

`top_movers` — one row per ticker per trading day (`UNIQUE (ticker, date)`), storing
direction (gainer/loser), % change, price, and volume. Schema in [db/schema.sql](db/schema.sql).
