"""
Deterministic synthetic data generator.

WHY THIS EXISTS: the live pipeline (ingest.py) pulls from yfinance / SEC EDGAR,
which need network access and sometimes API keys. To guarantee that someone can
clone the repo and run a full end-to-end demo with ZERO setup, we ship a
reproducible synthetic generator that creates realistic-looking prices and
fundamentals for the AI-compute universe from the spec.

Real data path: see ingest.py (`python -m data_pipeline.ingest --live`).
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

from .db import connect, init_db

# (ticker, name, sector, shares_out_millions, seed_price, drift, vol)
UNIVERSE = [
    ("NVDA", "NVIDIA Corp",            "Semiconductors", 2460, 120.0, 0.0009, 0.032),
    ("AMD",  "Advanced Micro Devices", "Semiconductors", 1620, 160.0, 0.0005, 0.034),
    ("AVGO", "Broadcom Inc",           "Semiconductors",  470, 170.0, 0.0006, 0.026),
    ("TSM",  "Taiwan Semiconductor",   "Semiconductors", 5190, 180.0, 0.0005, 0.024),
    ("ASML", "ASML Holding",           "Semiconductors",  393, 900.0, 0.0004, 0.025),
    ("MU",   "Micron Technology",      "Semiconductors", 1110,  95.0, 0.0003, 0.038),
    ("INTC", "Intel Corp",             "Semiconductors", 4280,  35.0,-0.0002, 0.030),
    ("MSFT", "Microsoft Corp",         "Software",       7430, 410.0, 0.0006, 0.018),
    ("GOOGL","Alphabet Inc",           "Software",      12100, 165.0, 0.0005, 0.020),
    ("META", "Meta Platforms",         "Software",       2540, 480.0, 0.0007, 0.026),
]

# Fundamentals roughly scaled per name (millions). Kept stylized but plausible.
FUNDAMENTALS = {
    "NVDA": dict(revenue=130000, ebitda=80000, net_income=63000, fcf=60000, total_debt=10000, cash=34000, equity=65000),
    "AMD":  dict(revenue=25800,  ebitda=4200,  net_income=1600,  fcf=3000,  total_debt=2200,  cash=5300,  equity=57000),
    "AVGO": dict(revenue=51600,  ebitda=27000, net_income=14000, fcf=19000, total_debt=66000, cash=9300,  equity=68000),
    "TSM":  dict(revenue=90000,  ebitda=58000, net_income=36000, fcf=29000, total_debt=29000, cash=68000, equity=170000),
    "ASML": dict(revenue=30000,  ebitda=10500, net_income=8200,  fcf=9000,  total_debt=4500,  cash=14000, equity=20000),
    "MU":   dict(revenue=25000,  ebitda=9000,  net_income=3500,  fcf=1200,  total_debt=13000, cash=8700,  equity=46000),
    "INTC": dict(revenue=53000,  ebitda=9000,  net_income=-1600, fcf=-2000, total_debt=50000, cash=24000, equity=99000),
    "MSFT": dict(revenue=245000, ebitda=136000,net_income=88000, fcf=74000, total_debt=45000, cash=75000, equity=268000),
    "GOOGL":dict(revenue=350000, ebitda=130000,net_income=100000,fcf=73000, total_debt=12000, cash=95000, equity=325000),
    "META": dict(revenue=164000, ebitda=87000, net_income=62000, fcf=54000, total_debt=37000, cash=70000, equity=183000),
}

TRADING_DAYS = 500  # ~2 years


def _factor_paths(n: int, rng: random.Random):
    """Shared market factor + per-sector factors so names realistically co-move."""
    market = [rng.gauss(0, 1) for _ in range(n)]
    sectors = {}
    for sec in sorted({u[2] for u in UNIVERSE}):
        sectors[sec] = [rng.gauss(0, 1) for _ in range(n)]
    return market, sectors


def _gbm_series(seed_price, drift, vol, sector, market, sector_shocks, rng):
    """
    GBM with a factor structure: each daily shock blends a market factor (0.5),
    a sector factor (0.35) and an idiosyncratic shock (0.79 ~= sqrt(1-.5^2-.35^2)).
    This produces positive within-sector correlation that the VaR covariance
    step then captures.
    """
    n = len(market)
    prices = [seed_price]
    sec = sector_shocks[sector]
    for t in range(n - 1):
        idio = rng.gauss(0, 1)
        shock = 0.50 * market[t] + 0.35 * sec[t] + 0.79 * idio
        prices.append(prices[-1] * math.exp(drift - 0.5 * vol**2 + vol * shock))
    return prices


def generate(seed: int = 42) -> None:
    init_db()
    rng = random.Random(seed)
    end = date.today()
    # business-day-ish calendar (skip weekends)
    days = []
    d = end
    while len(days) < TRADING_DAYS:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    days.reverse()

    with connect() as conn:
        conn.execute("DELETE FROM prices")
        conn.execute("DELETE FROM fundamentals")
        conn.execute("DELETE FROM companies")
        market, sector_shocks = _factor_paths(TRADING_DAYS, rng)
        for ticker, name, sector, shares, seed_px, drift, vol in UNIVERSE:
            conn.execute(
                "INSERT INTO companies(ticker,name,sector,shares_out) VALUES (?,?,?,?)",
                (ticker, name, sector, shares),
            )
            path = _gbm_series(seed_px, drift, vol, sector, market, sector_shocks, rng)
            rows = [
                (ticker, days[i].isoformat(), round(path[i], 2), round(rng.uniform(2e7, 8e7)))
                for i in range(TRADING_DAYS)
            ]
            conn.executemany("INSERT INTO prices(ticker,date,close,volume) VALUES (?,?,?,?)", rows)

            f = FUNDAMENTALS[ticker]
            conn.execute(
                """INSERT INTO fundamentals(ticker,period,revenue,ebitda,net_income,fcf,total_debt,cash,equity)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (ticker, "TTM", f["revenue"], f["ebitda"], f["net_income"],
                 f["fcf"], f["total_debt"], f["cash"], f["equity"]),
            )
    print(f"Generated synthetic data for {len(UNIVERSE)} tickers, {TRADING_DAYS} trading days each.")


if __name__ == "__main__":
    generate()
