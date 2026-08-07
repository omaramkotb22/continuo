"""Task 8a: backfill daily OHLCV for every ticker in top_movers, cache in the ohlcv table.

Uses yfinance (bulk, free) rather than Alpha Vantage (25 req/day free tier). Idempotent:
ON CONFLICT upsert, so re-running only refreshes/extends. Pulls a wide lookback window
so the 20-day volume average and 5-day trend are fully defined at each mover date.
"""
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]  # required (point at RDS or local)
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
LOOKBACK_DAYS = 60   # calendar days before the earliest mover date (covers 20 trading days)
CHUNK = 50           # tickers per yfinance request

UPSERT = """
INSERT INTO ohlcv (ticker, date, open, high, low, close, volume)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ticker, date) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, volume = EXCLUDED.volume;
"""


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def rows_from_frame(ticker: str, df) -> list[tuple]:
    out = []
    for ts, r in df.iterrows():
        close = r.get("Close")
        if close is None or close != close:  # skip NaN (ticker/day yfinance lacks)
            continue
        out.append((
            ticker, ts.date(),
            _num(r.get("Open")), _num(r.get("High")), _num(r.get("Low")),
            _num(close), _int(r.get("Volume")),
        ))
    return out


def _num(v):
    return None if v is None or v != v else float(v)


def _int(v):
    return None if v is None or v != v else int(v)


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA.read_text())
        tickers = [r[0] for r in conn.execute("SELECT DISTINCT ticker FROM top_movers ORDER BY ticker")]
        min_d, max_d = conn.execute("SELECT min(date), max(date) FROM top_movers").fetchone()
        start = (min_d - timedelta(days=LOOKBACK_DAYS)).isoformat()
        end = (max(max_d, date.today()) + timedelta(days=2)).isoformat()  # +2 for the next-day label
        print(f"{len(tickers)} tickers, OHLCV window {start} → {end}")

        total = 0
        for i, chunk in enumerate(chunked(tickers, CHUNK), 1):
            data = yf.download(chunk, start=start, end=end, group_by="ticker",
                               auto_adjust=False, progress=False, threads=True)
            batch = []
            for t in chunk:
                try:
                    df = data[t] if len(chunk) > 1 else data
                except KeyError:
                    continue
                batch += rows_from_frame(t, df.dropna(how="all"))
            if batch:
                conn.cursor().executemany(UPSERT, batch)
                conn.commit()
                total += len(batch)
            print(f"  chunk {i}: +{len(batch)} rows (running {total})")
        print(f"Done. Upserted {total} OHLCV rows.")


if __name__ == "__main__":
    main()
