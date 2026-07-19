"""Day 1: pull today's top gainers/losers from Alpha Vantage, print them, save raw JSON."""
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
URL = "https://www.alphavantage.co/query"
RAW_DIR = Path(__file__).parent / "data" / "raw"


def fetch_movers() -> dict:
    resp = requests.get(URL, params={"function": "TOP_GAINERS_LOSERS", "apikey": API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Alpha Vantage signals rate limits / bad keys via these keys instead of an HTTP error.
    if "top_gainers" not in data:
        sys.exit(f"Unexpected response (rate limit or bad key?):\n{json.dumps(data, indent=2)}")
    return data


def main() -> None:
    data = fetch_movers()
    for label, key in [("TOP GAINERS", "top_gainers"), ("TOP LOSERS", "top_losers")]:
        print(f"\n{label} ({data.get('last_updated', '?')})")
        for row in data[key][:5]:
            print(f"  {row['ticker']:<8} {row['price']:>10}  {row['change_percentage']:>8}  vol={row['volume']}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"movers_{date.today().isoformat()}.json"
    out.write_text(json.dumps(data, indent=2))
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
