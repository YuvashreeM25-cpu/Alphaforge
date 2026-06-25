"""
Monte-Carlo Value-at-Risk (Phase 3) — pure-Python reference implementation.

Simulates many correlated portfolio return paths and reports the loss quantile.
This always runs (no build step). The C++ version in risk/cpp/ produces the same
numbers far faster; risk/benchmark.py proves the speedup. The point of the C++
port is judgment: knowing WHEN a hot loop justifies dropping to a fast language.
"""
from __future__ import annotations

import numpy as np

from data_pipeline.db import connect


def _returns_matrix(tickers: list[str]) -> tuple[np.ndarray, list[str]]:
    series = {}
    with connect() as conn:
        for t in tickers:
            rows = conn.execute(
                "SELECT date, close FROM prices WHERE ticker=? ORDER BY date", (t,)
            ).fetchall()
            closes = np.array([r["close"] for r in rows], dtype=float)
            if len(closes) > 2:
                series[t] = np.diff(np.log(closes))
    if not series:
        raise ValueError("no return data")
    n = min(len(v) for v in series.values())
    used = list(series.keys())
    mat = np.column_stack([series[t][-n:] for t in used])
    return mat, used


def monte_carlo_var(tickers, weights=None, n_paths=100_000, horizon_days=1,
                    confidence=0.95, seed=7):
    """
    Returns 1-day (or horizon) VaR and CVaR as a positive fraction of portfolio
    value at the given confidence level, plus the simulated mean/vol.
    """
    rng = np.random.default_rng(seed)
    rets, used = _returns_matrix(list(tickers))
    if weights is None:
        weights = np.ones(len(used)) / len(used)
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()

    mu = rets.mean(axis=0)
    cov = np.cov(rets, rowvar=False)
    # Cholesky for correlated normal draws
    L = np.linalg.cholesky(cov + 1e-12 * np.eye(len(used)))

    # simulate horizon as sum of daily shocks
    port_losses = np.empty(n_paths)
    for d in range(horizon_days):
        z = rng.standard_normal((n_paths, len(used)))
        daily = mu + z @ L.T
        port_ret = daily @ weights
        if d == 0:
            cum = port_ret.copy()
        else:
            cum += port_ret
    port_losses = -cum  # loss = negative return

    var = float(np.quantile(port_losses, confidence))
    cvar = float(port_losses[port_losses >= var].mean())
    return {
        "tickers": used,
        "weights": [round(float(w), 3) for w in weights],
        "n_paths": n_paths,
        "horizon_days": horizon_days,
        "confidence": confidence,
        "VaR_pct": round(var * 100, 3),
        "CVaR_pct": round(cvar * 100, 3),
        "sim_mean_pct": round(float(-port_losses.mean()) * 100, 4),
        "sim_vol_pct": round(float(port_losses.std()) * 100, 3),
    }


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    print(monte_carlo_var(["NVDA", "AMD", "TSM"], n_paths=200_000))
