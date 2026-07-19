"""Day 3: plot the latest trading day's top movers as a bar chart, save a PNG.

Reads from Postgres (the rows fetch_movers.py ingested). Two panels — gainers and
losers — each a single-hue horizontal bar chart sorted by magnitude, with direct
value labels so the sign never relies on color alone (CVD-safe blue/red poles).
"""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; no display needed
import matplotlib.pyplot as plt
import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://continuo:continuo@localhost:5433/continuo")
REPORTS = Path(__file__).parent / "reports"
TOP_N = 10

# Palette (dataviz skill reference, validated CVD-safe): diverging poles + neutral ink.
GAINER, LOSER = "#2a78d6", "#e34948"
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#898781", "#e1e0d9"


def latest_movers() -> tuple[str, list, list]:
    with psycopg.connect(DATABASE_URL) as conn:
        (day,) = conn.execute("SELECT max(date) FROM top_movers").fetchone()
        if day is None:
            raise SystemExit("No rows in top_movers — run fetch_movers.py first.")
        rows = conn.execute(
            "SELECT ticker, direction, pct_change FROM top_movers WHERE date = %s", (day,)
        ).fetchall()
    gainers = sorted([r for r in rows if r[1] == "gainer"], key=lambda r: r[2], reverse=True)[:TOP_N]
    losers = sorted([r for r in rows if r[1] == "loser"], key=lambda r: r[2])[:TOP_N]
    return str(day), gainers, losers


def _panel(ax, data, color, title):
    tickers = [r[0] for r in data][::-1]  # largest magnitude on top
    values = [float(r[2]) for r in data][::-1]
    ax.barh(tickers, values, color=color, height=0.68, zorder=3)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=8)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    pad = max(abs(v) for v in values) * 0.02
    for y, v in enumerate(values):
        ax.text(v + (pad if v >= 0 else -pad), y, f"{v:+.1f}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=8, color=INK)
    lo, hi = min(values + [0]), max(values + [0])
    ax.set_xlim(lo - abs(lo) * 0.12 - pad, hi + abs(hi) * 0.12 + pad)


def main() -> None:
    day, gainers, losers = latest_movers()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), facecolor=SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
    _panel(ax1, gainers, GAINER, "Top gainers")
    _panel(ax2, losers, LOSER, "Top losers")
    fig.suptitle(f"Continuo — top movers, {day}", x=0.02, y=0.98, ha="left",
                 fontsize=15, fontweight="bold", color=INK)
    fig.text(0.02, 0.915, "% change on the mover day · source: Alpha Vantage",
             ha="left", fontsize=9, color=MUTED)
    fig.tight_layout(rect=[0, 0, 1, 0.88])

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"movers_{day}.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
