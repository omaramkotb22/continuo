"""Task 10: walk-forward backtest — no lookahead. For each trading day T (after a warmup of
MIN_TRAIN_DATES days), train on every mover with mover_date < T, predict the movers ON day T,
then roll forward. Predictions are all strictly out-of-sample; we aggregate them and report
precision/recall/AUC/accuracy against the base rate — the honest evaluation.
"""
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from dataset import FEATURE_COLS, load_features, make_model, metrics

load_dotenv()
MIN_TRAIN_DATES = 4  # warmup before the first prediction day


def walk_forward(df: pd.DataFrame):
    """Return (y_true, proba, n_folds) of concatenated out-of-sample predictions."""
    dates = sorted(df["mover_date"].unique())
    y_all, p_all, folds = [], [], 0
    for T in dates[MIN_TRAIN_DATES:]:
        train = df[df["mover_date"] < T]
        test = df[df["mover_date"] == T]
        if train["label"].nunique() < 2 or test.empty:
            continue  # need both classes to train a probability
        model = make_model()
        model.fit(train[FEATURE_COLS], train["label"])
        y_all.append(test["label"].to_numpy())
        p_all.append(model.predict_proba(test[FEATURE_COLS])[:, 1])
        folds += 1
    if not y_all:
        return pd.Series([], dtype=int), np.array([]), 0
    return pd.Series(np.concatenate(y_all)), np.concatenate(p_all), folds


def main() -> None:
    df = load_features()
    dates = df["mover_date"].nunique()
    if dates <= MIN_TRAIN_DATES:
        raise SystemExit(f"Only {dates} trading days — need > {MIN_TRAIN_DATES} to walk forward.")
    y, p, folds = walk_forward(df)
    if folds == 0:
        raise SystemExit("No usable walk-forward folds (train never had both classes).")
    print(f"walk-forward: {folds} folds, {dates} dates, {len(y)} out-of-sample predictions")
    print("aggregate OOS:", metrics(y, p))
    print(f"(a coin-flip baseline scores AUC 0.5; base rate {y.mean():.1%} is the "
          f"accuracy of always predicting the majority class)")


if __name__ == "__main__":
    main()
