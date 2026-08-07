"""Task 9 + 12: baseline XGBoost with a TIME-ORDERED split (no shuffling — this is a time
series), then ship a versioned artifact.

Reports two honest numbers: the 70/30 time-holdout metrics and the walk-forward OOS metrics
(the estimate we trust). The shipped model is retrained on ALL labelled data for inference and
written as models/xgb_v{n}.json with a metrics.json alongside — uploaded to S3 when MODEL_BUCKET
is set (mirrors the ingestion S3 pattern).
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from backtest import walk_forward
from dataset import FEATURE_COLS, PARAMS, load_features, make_model, metrics, time_split_date

load_dotenv()
MODELS_DIR = Path(os.getenv("MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))


def next_version(models_dir: Path) -> int:
    models_dir.mkdir(parents=True, exist_ok=True)
    ns = [int(m.group(1)) for f in models_dir.glob("xgb_v*.json")
          if (m := re.fullmatch(r"xgb_v(\d+)\.json", f.name))]
    return max(ns, default=0) + 1


def holdout_metrics(df) -> dict:
    split = time_split_date(df, train_frac=0.7)
    train, test = df[df["mover_date"] <= split], df[df["mover_date"] > split]
    if test.empty:
        return {"note": "test split empty — need more trading days"}
    model = make_model()
    model.fit(train[FEATURE_COLS], train["label"])
    proba = model.predict_proba(test[FEATURE_COLS])[:, 1]
    m = metrics(test["label"], proba)
    m["split_date"], m["n_train"] = str(split.date()), int(len(train))
    return m


def main() -> None:
    df = load_features()
    n_dates = df["mover_date"].nunique()
    print(f"rows={len(df)}  dates={n_dates}  positives={int(df['label'].sum())} ({df['label'].mean():.1%})")

    holdout = holdout_metrics(df)
    print("holdout (70/30 time split):", holdout)

    y, p, folds = walk_forward(df)
    wf = metrics(y, p) | {"folds": folds} if folds else {"note": "insufficient dates"}
    print("walk-forward OOS:", wf)

    # Ship a model retrained on ALL labelled data (for inference).
    final = make_model()
    final.fit(df[FEATURE_COLS], df["label"])
    version = next_version(MODELS_DIR)
    model_path = MODELS_DIR / f"xgb_v{version}.json"
    metrics_path = MODELS_DIR / f"xgb_v{version}.metrics.json"
    final.save_model(model_path)

    report = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_rows": int(len(df)), "n_dates": int(n_dates),
        "label_positive_rate": round(float(df["label"].mean()), 3),
        "features": FEATURE_COLS,
        "params": PARAMS,
        "holdout_time_split": holdout,
        "walk_forward_oos": wf,
        "feature_importances": dict(sorted(
            zip(FEATURE_COLS, [round(float(x), 3) for x in final.feature_importances_]),
            key=lambda kv: -kv[1])),
    }
    metrics_path.write_text(json.dumps(report, indent=2))
    print(f"saved {model_path.name} + {metrics_path.name} in {MODELS_DIR}")

    bucket = os.getenv("MODEL_BUCKET")
    if bucket:
        import boto3
        s3 = boto3.client("s3")
        for path in (model_path, metrics_path):
            s3.upload_file(str(path), bucket, f"models/{path.name}")
        print(f"uploaded models/{model_path.name} + metrics to s3://{bucket}/models/")


if __name__ == "__main__":
    main()
