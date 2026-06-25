"""
Feature engineering (Phase 2).

Builds a supervised dataset to predict: "does this stock outperform its sector
over the next H trading days?" Features are computed only from information
available AT each date — this is where lookahead leakage hides, so we are
deliberately careful (see train_classifier.py for the time-aware split).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_pipeline.db import connect

HORIZON = 21  # ~1 trading month forward


def _load_prices() -> pd.DataFrame:
    with connect() as conn:
        df = conn.read_df(
            "SELECT p.ticker, p.date, p.close, c.sector "
            "FROM prices p JOIN companies c ON p.ticker=c.ticker "
            "ORDER BY p.ticker, p.date"
        )
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_dataset() -> pd.DataFrame:
    df = _load_prices().sort_values(["ticker", "date"]).copy()
    out = []
    # sector average daily close (for relative-performance label)
    df["ret1"] = df.groupby("ticker")["close"].pct_change()

    for ticker, g in df.groupby("ticker"):
        g = g.reset_index(drop=True)
        g["mom_21"] = g["close"].pct_change(21)          # trailing 1m momentum
        g["mom_63"] = g["close"].pct_change(63)          # trailing 3m momentum
        g["vol_21"] = g["ret1"].rolling(21).std()        # realized vol
        g["ma_gap"] = g["close"] / g["close"].rolling(50).mean() - 1  # vs 50d MA
        # forward return (the thing we will compare to sector) — used for label only
        g["fwd_ret"] = g["close"].shift(-HORIZON) / g["close"] - 1
        out.append(g)

    full = pd.concat(out, ignore_index=True)

    # sector forward return = mean forward return across tickers in that sector/date
    sector_fwd = (full.groupby(["sector", "date"])["fwd_ret"]
                  .transform("mean"))
    full["label"] = (full["fwd_ret"] > sector_fwd).astype(int)

    feature_cols = ["mom_21", "mom_63", "vol_21", "ma_gap"]
    full = full.dropna(subset=feature_cols + ["fwd_ret"]).reset_index(drop=True)
    full.attrs["feature_cols"] = feature_cols
    return full


FEATURE_COLS = ["mom_21", "mom_63", "vol_21", "ma_gap"]


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    ds = build_dataset()
    print(ds[["ticker", "date"] + FEATURE_COLS + ["label"]].tail())
    print("rows:", len(ds), "| positive rate:", round(ds["label"].mean(), 3))
