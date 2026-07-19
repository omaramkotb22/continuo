"""Ingest today's Alpha Vantage top gainers/losers: save raw JSON + upsert into Postgres.

Idempotent: re-running for the same trading date updates rows in place (no duplicates).
"""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://continuo:continuo@localhost:5433/continuo")
URL = "https://www.alphavantage.co/query"
ROOT = Path(__file__).parent
# Overridable so the Lambda container can write to /tmp (its only writable path).
RAW_DIR = Path(os.getenv("RAW_DIR", ROOT / "data" / "raw"))
SCHEMA = ROOT / "db" / "schema.sql"

UPSERT = """
INSERT INTO top_movers (ticker, date, direction, pct_change, price, volume)
VALUES (%(ticker)s, %(date)s, %(direction)s, %(pct_change)s, %(price)s, %(volume)s)
ON CONFLICT (ticker, date) DO UPDATE SET
    direction  = EXCLUDED.direction,
    pct_change = EXCLUDED.pct_change,
    price      = EXCLUDED.price,
    volume     = EXCLUDED.volume;
"""


def fetch_movers() -> dict:
    resp = requests.get(URL, params={"function": "TOP_GAINERS_LOSERS", "apikey": API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Alpha Vantage signals rate limits / bad keys via these keys instead of an HTTP error.
    if "top_gainers" not in data:
        sys.exit(f"Unexpected response (rate limit or bad key?):\n{json.dumps(data, indent=2)}")
    return data


def parse_rows(data: dict) -> list[dict]:
    """Flatten gainers + losers into DB rows. most_actively_traded is ignored (schema is gainer/loser)."""
    trading_date = datetime.strptime(data["last_updated"].split()[0], "%Y-%m-%d").date()
    rows = []
    for direction, key in [("gainer", "top_gainers"), ("loser", "top_losers")]:
        for r in data[key]:
            rows.append({
                "ticker": r["ticker"],
                "date": trading_date,
                "direction": direction,
                "pct_change": float(r["change_percentage"].rstrip("%")),
                "price": float(r["price"]),
                "volume": int(r["volume"]),
            })
    return rows


def save_raw(data: dict) -> str:
    """Archive raw JSON. Uploads to S3 when RAW_BUCKET is set (AWS), else writes locally."""
    key = f"raw/movers_{date.today().isoformat()}.json"
    payload = json.dumps(data, indent=2)
    bucket = os.getenv("RAW_BUCKET")
    if bucket:
        import boto3  # provided by the Lambda base image; not a local dev dep
        boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=payload.encode())
        return f"s3://{bucket}/{key}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"movers_{date.today().isoformat()}.json"
    out.write_text(payload)
    return str(out)


def store(rows: list[dict]) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA.read_text())  # ensure table exists (idempotent)
        with conn.cursor() as cur:
            cur.executemany(UPSERT, rows)
    print(f"Upserted {len(rows)} rows into top_movers.")


def run() -> dict:
    """Full ingestion pipeline. Returns a summary (used as the Lambda response)."""
    data = fetch_movers()
    rows = parse_rows(data)
    raw_path = save_raw(data)
    store(rows)
    return {"date": str(rows[0]["date"]), "rows": len(rows), "raw": str(raw_path)}


def main() -> None:
    summary = run()
    print(f"Fetched {summary['rows']} movers for {summary['date']} "
          f"(raw: {Path(summary['raw']).name}); upserted into top_movers.")


if __name__ == "__main__":
    main()
