"""Task 8b: build the v1 feature set + next-day label into the features table.

For each mover (ticker, mover_date) we compute, using OHLCV known at/before the mover-day
close:
  gap_pct     = (mover-day open - prior close) / prior close
  pct_change  = mover-day % change (from top_movers)
  rel_volume  = mover-day volume / trailing 20-day avg volume
  trend_5d    = % return over the 5 trading days before the mover day
  day_of_week = 0..4
Label uses the NEXT trading day only: 1 if next close > mover-day close (close-vs-close).
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

FEATURES = ["gap_pct", "pct_change", "rel_volume", "trend_5d"]  # numeric predictors that must be present

UPSERT = """
INSERT INTO features (ticker, mover_date, direction, gap_pct, pct_change, rel_volume,
                      trend_5d, day_of_week, target_date, label)
VALUES (%(ticker)s, %(mover_date)s, %(direction)s, %(gap_pct)s, %(pct_change)s, %(rel_volume)s,
        %(trend_5d)s, %(day_of_week)s, %(target_date)s, %(label)s)
ON CONFLICT (ticker, mover_date) DO UPDATE SET
    direction=EXCLUDED.direction, gap_pct=EXCLUDED.gap_pct, pct_change=EXCLUDED.pct_change,
    rel_volume=EXCLUDED.rel_volume, trend_5d=EXCLUDED.trend_5d, day_of_week=EXCLUDED.day_of_week,
    target_date=EXCLUDED.target_date, label=EXCLUDED.label;
"""


def load_df(conn, sql) -> pd.DataFrame:
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA.read_text())
        movers = load_df(conn, "SELECT ticker, date AS mover_date, direction, pct_change FROM top_movers")
        ohlcv = load_df(conn, "SELECT ticker, date, open, high, low, close, volume FROM ohlcv")

    if ohlcv.empty:
        raise SystemExit("ohlcv is empty — run backfill_ohlcv.py first.")

    # Numeric + sorted per ticker/date so the shift/rolling windows are correct.
    for c in ["open", "high", "low", "close", "volume"]:
        ohlcv[c] = pd.to_numeric(ohlcv[c])
    ohlcv = ohlcv.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = ohlcv.groupby("ticker", group_keys=False)

    ohlcv["prior_close"] = g["close"].shift(1)
    ohlcv["close_5_ago"] = g["close"].shift(6)   # 5 trading days before the prior day
    ohlcv["avg_vol_20"] = g["volume"].transform(lambda s: s.shift(1).rolling(20, min_periods=10).mean())
    ohlcv["next_close"] = g["close"].shift(-1)
    ohlcv["next_date"] = g["date"].shift(-1)

    ohlcv["gap_pct"] = (ohlcv["open"] - ohlcv["prior_close"]) / ohlcv["prior_close"] * 100
    ohlcv["rel_volume"] = ohlcv["volume"] / ohlcv["avg_vol_20"]
    ohlcv["trend_5d"] = (ohlcv["prior_close"] - ohlcv["close_5_ago"]) / ohlcv["close_5_ago"] * 100
    ohlcv["label"] = (ohlcv["next_close"] > ohlcv["close"]).astype("Int64")
    ohlcv.loc[ohlcv["next_close"].isna(), "label"] = pd.NA  # no next day yet → no label

    feat = movers.merge(
        ohlcv[["ticker", "date", "gap_pct", "rel_volume", "trend_5d", "next_date", "label"]],
        left_on=["ticker", "mover_date"], right_on=["ticker", "date"], how="left",
    )
    feat["pct_change"] = pd.to_numeric(feat["pct_change"])
    feat["day_of_week"] = pd.to_datetime(feat["mover_date"]).dt.weekday

    total = len(feat)
    # Penny stocks can make a divisor ~0 → inf; treat those as missing and drop.
    feat[FEATURES] = feat[FEATURES].replace([np.inf, -np.inf], np.nan)
    feat = feat.dropna(subset=FEATURES + ["label"])
    print(f"movers={total}  usable features (OHLCV found + labelled)={len(feat)}  dropped={total - len(feat)}")

    rows = [{
        "ticker": r.ticker, "mover_date": r.mover_date, "direction": r.direction,
        "gap_pct": float(r.gap_pct), "pct_change": float(r.pct_change),
        "rel_volume": float(r.rel_volume), "trend_5d": float(r.trend_5d),
        "day_of_week": int(r.day_of_week),
        "target_date": r.next_date, "label": int(r.label),
    } for r in feat.itertuples()]

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("TRUNCATE features")  # fully derived table — rebuild clean, no stale rows
        conn.cursor().executemany(UPSERT, rows)
        conn.commit()
    pos = sum(x["label"] for x in rows)
    print(f"Wrote {len(rows)} feature rows. Label balance: {pos} up / {len(rows) - pos} down "
          f"({pos / len(rows):.1%} positive).")


if __name__ == "__main__":
    main()
