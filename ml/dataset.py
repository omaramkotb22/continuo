"""Shared feature loading, encoding, model config + metrics — used by train.py and backtest.py
(one definition, no drift)."""
import os

import pandas as pd
import psycopg
import xgboost as xgb
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             roc_auc_score)

# Model input columns. direction -> is_gainer (continuation is a different problem per side).
FEATURE_COLS = ["gap_pct", "pct_change", "rel_volume", "trend_5d", "day_of_week", "is_gainer"]

# Modest + regularized: the dataset is small, so keep the model shallow.
PARAMS = dict(
    max_depth=3, n_estimators=150, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
    eval_metric="logloss", n_jobs=4, random_state=0,
)


def make_model() -> "xgb.XGBClassifier":
    return xgb.XGBClassifier(**PARAMS)


def metrics(y_true, proba, thresh: float = 0.5) -> dict:
    """Report precision/recall/AUC + base rate — not just accuracy."""
    pred = (proba >= thresh).astype(int)
    out = {
        "n": int(len(y_true)),
        "base_rate": round(float(y_true.mean()), 3),
        "accuracy": round(accuracy_score(y_true, pred), 3),
        "precision": round(precision_score(y_true, pred, zero_division=0), 3),
        "recall": round(recall_score(y_true, pred, zero_division=0), 3),
    }
    out["auc"] = round(roc_auc_score(y_true, proba), 3) if y_true.nunique() > 1 else None
    return out


def load_features(database_url: str | None = None) -> pd.DataFrame:
    url = database_url or os.environ["DATABASE_URL"]
    with psycopg.connect(url) as conn:
        cur = conn.execute(
            "SELECT ticker, mover_date, direction, gap_pct, pct_change, rel_volume, "
            "trend_5d, day_of_week, label FROM features ORDER BY mover_date, ticker"
        )
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    if df.empty:
        raise SystemExit("features table is empty — run backfill_ohlcv.py then build_features.py.")
    df["is_gainer"] = (df["direction"] == "gainer").astype(int)
    for c in ["gap_pct", "pct_change", "rel_volume", "trend_5d"]:
        df[c] = pd.to_numeric(df[c])
    df["day_of_week"] = df["day_of_week"].astype(int)
    df["label"] = df["label"].astype(int)
    df["mover_date"] = pd.to_datetime(df["mover_date"])
    return df


def time_split_date(df: pd.DataFrame, train_frac: float = 0.7):
    """Return the last training date such that whole dates stay together and ~train_frac of rows train."""
    by_date = df.groupby("mover_date").size().sort_index()
    cum = by_date.cumsum() / len(df)
    # first date whose cumulative row share reaches train_frac becomes the train/test boundary
    return cum.index[(cum >= train_frac).argmax()]
