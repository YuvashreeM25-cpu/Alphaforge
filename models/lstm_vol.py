"""
Deep-learning model (Phase 2) — LSTM volatility forecaster.  [OPTIONAL]

WHY A NEURAL NET HERE vs the classic GBM classifier:
The GBM model predicts a binary cross-sectional label from a handful of
engineered features. Volatility, by contrast, is a SEQUENCE problem — today's
realized vol depends on the recent path in an order-dependent, autocorrelated
way (vol clustering). An LSTM consumes the raw return sequence and learns that
temporal structure directly, instead of us hand-crafting lag features. That is
the honest reason to reach for a sequence model here.

This file is optional: it needs `pip install torch`. The rest of AlphaForge
runs without it. Run:  python -m models.lstm_vol
"""
from __future__ import annotations

import numpy as np

try:
    import torch
    import torch.nn as nn
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False

from data_pipeline.db import connect

LOOKBACK = 20  # days of returns fed to the LSTM
HORIZON = 5    # predict realized vol over next 5 days


def _sequences(ticker: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT close FROM prices WHERE ticker=? ORDER BY date", (ticker,)
        ).fetchall()
    closes = np.array([r["close"] for r in rows], dtype=np.float32)
    rets = np.diff(np.log(closes))
    X, y = [], []
    for i in range(LOOKBACK, len(rets) - HORIZON):
        X.append(rets[i - LOOKBACK:i])
        y.append(rets[i:i + HORIZON].std())   # forward realized vol (target)
    return np.array(X, dtype=np.float32)[..., None], np.array(y, dtype=np.float32)


if HAVE_TORCH:
    class VolLSTM(nn.Module):
        def __init__(self, hidden=32):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)


def train(ticker: str = "NVDA", epochs: int = 30):
    if not HAVE_TORCH:
        print("PyTorch not installed. Run: pip install torch")
        return
    X, y = _sequences(ticker)
    # time-ordered split (no shuffling — same anti-leakage discipline)
    n = len(X)
    cut = int(n * 0.8)
    Xtr, ytr = torch.tensor(X[:cut]), torch.tensor(y[:cut])
    Xte, yte = torch.tensor(X[cut:]), torch.tensor(y[cut:])

    model = VolLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    lossf = nn.MSELoss()
    for ep in range(epochs):
        model.train(); opt.zero_grad()
        loss = lossf(model(Xtr), ytr)
        loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        test_mse = lossf(model(Xte), yte).item()
        # naive baseline: predict trailing vol = last window's std
        baseline = np.mean((X[cut:, :, 0].std(axis=1) - y[cut:]) ** 2)
    print(f"{ticker}  LSTM test MSE={test_mse:.2e}  naive-baseline MSE={baseline:.2e}")
    print("If LSTM MSE < baseline, the sequence model added value over 'vol persists'.")
    return model


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    train("NVDA")
