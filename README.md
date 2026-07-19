# Continuo

Will today's top mover keep moving tomorrow? A backend-first ML pipeline that ingests daily stock-market "top movers," engineers features, trains a next-day continuation classifier, and serves predictions over a REST API. Portfolio project — not for live trading.

See [CONTINUO.md](CONTINUO.md) for the full plan and task breakdown.

## Day 1 — see real data

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste your Alpha Vantage key into .env
python fetch_movers.py        # prints top movers, saves data/raw/movers_YYYY-MM-DD.json
```
