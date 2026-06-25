"""Inference helper: latest P(outperform) for a ticker (Phase 2 / Phase 4 tool)."""
from __future__ import annotations

import pandas as pd

from .features import FEATURE_COLS, build_dataset
from .train_classifier import load


def predict_latest(ticker: str) -> dict:
    model = load()
    ds = build_dataset()
    g = ds[ds["ticker"] == ticker].sort_values("date")
    if g.empty:
        return {"ticker": ticker, "error": "no features available"}
    latest = g.iloc[[-1]]
    prob = float(model.predict_proba(latest[FEATURE_COLS])[:, 1][0])
    return {
        "ticker": ticker,
        "p_outperform_sector_1m": round(prob, 3),
        "as_of": str(latest["date"].iloc[0].date()),
        "features": {c: round(float(latest[c].iloc[0]), 4) for c in FEATURE_COLS},
    }


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    print(predict_latest("NVDA"))
