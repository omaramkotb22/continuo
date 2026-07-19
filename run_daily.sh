#!/usr/bin/env bash
# Daily ingestion wrapper for cron. Ensures Postgres is up, ingests movers, redraws chart.
# Idempotent: safe to run repeatedly for the same trading day.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"
mkdir -p logs
LOG="logs/ingest.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >>"$LOG"
{
  docker compose up -d db
  ./.venv/bin/python fetch_movers.py
  ./.venv/bin/python plot_movers.py
} >>"$LOG" 2>&1
echo "done" >>"$LOG"
