"""AWS Lambda entry point for the ingestion container image.

The event/context are unused — ingestion is a scheduled, parameterless job. Env
(ALPHA_VANTAGE_API_KEY, DATABASE_URL, RAW_DIR) is injected by the Lambda config.
"""
from fetch_movers import run


def handler(event, context):
    summary = run()
    print(f"ingest ok: {summary}")
    return summary
