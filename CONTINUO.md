# Continuo

**Will today's top mover keep moving tomorrow?**

A backend-first ML pipeline that ingests daily stock market "top movers," engineers features, trains a classifier to predict next-day continuation, and serves predictions through a REST API. No frontend — the deliverable is the pipeline, the API, and the engineering discipline behind them (backtesting methodology, IaC, CI/CD, observability).

Built as a portfolio/resume project for backend engineering, DevOps, and SRE roles. Not intended for live trading or financial decision-making — see "Non-goals" below.

---

## Goals

- Demonstrate a production-shaped data pipeline: scheduled ingestion → storage → feature engineering → training → inference → serving.
- Demonstrate infra-as-code and cloud-native deployment on AWS.
- Demonstrate rigorous ML practice: walk-forward backtesting, no lookahead bias, honest metrics reporting (not just accuracy).
- Ship something visibly working within the first 3 days to stay motivating, then layer in AWS infra afterward.

## Non-goals

- Not a trading bot. No order execution, no real capital at risk.
- Not a UI project. No frontend, no dashboard — API responses and README docs are the interface.
- Not claiming alpha. The honest expected outcome is "model performs near chance on out-of-sample data" — that finding, well documented, is itself part of the deliverable.

---

## Tech stack

- **Language:** Python 3.11+
- **Local dev:** Docker Compose, Postgres
- **Data source:** Alpha Vantage `TOP_GAINERS_LOSERS` + historical OHLCV endpoints (free tier)
- **ML:** pandas, XGBoost, scikit-learn (walk-forward validation, no k-fold shuffling — this is time series)
- **API:** FastAPI
- **Cloud:** AWS — S3, RDS (or Aurora Serverless v2), Lambda, ECS Fargate, EventBridge, API Gateway or ALB, CloudWatch
- **IaC:** Terraform
- **CI/CD:** GitHub Actions (lint, test, `terraform plan` on PR; build + deploy on merge)
- **Stretch:** Claude API for headline sentiment / catalyst classification as an additional engineered feature (not as the predictor itself)

---

## Architecture (target state, after week 1 of AWS migration)

```
EventBridge (daily cron, after market close)
  -> Ingestion Lambda (pulls movers + OHLCV from Alpha Vantage)
    -> S3 (raw JSON) + RDS Postgres (normalized features)
      -> Training job on Fargate (nightly retrain, XGBoost)
        -> Model registry (S3, versioned artifacts)
          -> Inference Lambda (scores today's top movers)
            -> FastAPI on Fargate (serves predictions via API)
```

Days 1–3 run entirely locally (no AWS) — see task breakdown below.

---

## Data model (initial)

**Table: `top_movers`**
| column | type | notes |
|---|---|---|
| id | serial PK | |
| ticker | text | |
| date | date | |
| direction | text | 'gainer' or 'loser' |
| pct_change | numeric | |
| price | numeric | |
| volume | bigint | |
| avg_volume_20d | numeric | for relative volume feature |
| created_at | timestamp | |

**Table: `predictions`** (added in week 3)
| column | type | notes |
|---|---|---|
| id | serial PK | |
| ticker | text | |
| prediction_date | date | date the prediction was made |
| target_date | date | the "next day" being predicted |
| probability_continues | numeric | model output |
| actual_outcome | boolean | filled in the day after target_date, nullable until then |
| model_version | text | ties to the S3 model artifact version |

---

## Feature list (v1)

- Gap % (open vs prior close)
- % change on the mover day
- Relative volume (volume / 20-day average volume)
- 5-day price trend prior to the mover day
- Day of week
- Direction (gainer vs loser) — predicting continuation is a different problem for each

Label: whether `close` on `target_date` (next trading day) is above `close` on the mover day. Lock in close-vs-close (not intraday high) as the target before writing feature code, for consistency.

---

## Task breakdown

### Day 1 — see real data, nothing else (no AWS, no DB)
1. Create GitHub repo, one-line README. **Done when:** repo exists on GitHub.
2. Sign up for free Alpha Vantage API key, store in `.env` (gitignored). **Done when:** key saved locally, not committed.
3. Write a ~10-line script calling `TOP_GAINERS_LOSERS`, print the result. **Done when:** terminal shows real tickers with real prices.
4. Save the response to a local dated JSON file. **Done when:** a file with today's date contains today's movers.

### Day 2 — store it locally
1. `docker-compose up` a local Postgres. **Done when:** `docker ps` shows it running.
2. Create the `top_movers` table (see schema above). **Done when:** `\d top_movers` in psql shows the table.
3. Change the day 1 script to insert rows instead of printing. **Done when:** running it adds rows.
4. Query the table. **Done when:** `SELECT * FROM top_movers` returns real rows.

### Day 3 — make it visible and automatic
1. Plot today's movers as a bar chart (matplotlib), save as PNG. **Done when:** you have an image worth screenshotting.
2. Add a local cron/launchd job to run ingestion daily after market close. **Done when:** `crontab -l` shows the entry.
3. Push to GitHub with a real README (3-sentence project summary). **Done when:** repo is public with a real description.

### Days 4–7 — migrate to AWS
4. Containerize the ingestion script (Dockerfile, tested locally). **Done when:** `docker run` reproduces day 1–2 behavior.
5. Terraform: S3 bucket + RDS instance (or Aurora Serverless v2). **Done when:** `terraform apply` succeeds, resources visible in AWS console.
6. Terraform: Lambda (from the container image) + EventBridge rule. **Done when:** manually invoking the Lambda inserts a row into RDS.
7. Cut over from local cron to EventBridge, confirm an unattended run. **Done when:** a row appears in RDS the next morning without you doing anything.

### Week 2 — ML sprint
8. Feature engineering script producing the v1 feature set above from raw data.
9. Baseline model in a notebook: XGBoost binary classifier, train/test split respecting time order (no shuffling).
10. Walk-forward backtest harness: train on data up to date T, predict T+1, roll forward. Track precision, recall, AUC — not just accuracy.
11. Package training as a script, then as an ECS Fargate task definition (Terraform).
12. Model artifact versioning to S3 (e.g. `models/xgb_v{n}.json` + a metrics.json alongside it).

### Week 3 — serving + polish
13. Inference Lambda: loads latest model from S3, scores today's movers, writes to `predictions` table.
14. Label-filling job: nightly, updates `actual_outcome` for yesterday's predictions using today's close data.
15. FastAPI service with `GET /predictions/today`, `GET /predictions/{ticker}/history`, `GET /model/metrics`.
16. Deploy FastAPI to Fargate (or Lambda + API Gateway), Terraform-managed.
17. CloudWatch dashboard + alarm on pipeline failure and on model accuracy drift.
18. README pass: architecture diagram, metrics writeup, explicit "known limitations" section.

### Week 4+ — stretch goals
19. Headline sentiment feature: pull news per ticker, use Claude API with a structured output prompt to classify catalyst type (earnings, FDA, insider, social/meme, macro, unclear) and sentiment score.
20. A/B comparison: does adding the sentiment feature improve out-of-sample AUC vs the v1 model? Document the result either way.
21. Claude-generated plain-English rationale per prediction, referencing actual feature values, for API response polish.

---

## Notes for Claude Code

- Respect the day-by-day order above — do not skip ahead to AWS/Terraform before the local pipeline (days 1–3) is working end to end.
- Time-series discipline matters more than model sophistication: never let the train/test split leak future data into training. Use walk-forward validation only.
- Keep IAM roles least-privilege in every Terraform module.
- Every scheduled job should be idempotent — safe to re-run for the same date without creating duplicate rows.
- Favor small, working increments over large speculative scaffolding — each numbered task above should be independently committable.