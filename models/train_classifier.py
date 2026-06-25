"""
Classic ML model (Phase 2): predict P(outperform sector next month).

THE IMPORTANT PART — TIME-AWARE VALIDATION.
In finance ML, a random train/test split leaks the future into the past: rows
from the same week end up on both sides, and momentum/vol features carry
overlapping information, so the model looks great in backtest and dies live.
We instead split STRICTLY BY DATE: train on the earliest 60%, validate on the
next 20%, test on the most recent 20%. No future row is ever seen in training.

We report honest metrics AND where the model is weak. A model that admits its
limits reads as senior; one that claims 0.99 AUC reads as leaked.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_COLS, build_dataset

MODEL_PATH = Path(__file__).resolve().parent / "classifier.joblib"
METRICS_PATH = Path(__file__).resolve().parent / "classifier_metrics.json"


def _time_split(df):
    df = df.sort_values("date").reset_index(drop=True)
    dates = df["date"].sort_values().unique()
    train_cut = dates[int(len(dates) * 0.60)]
    val_cut = dates[int(len(dates) * 0.80)]
    train = df[df["date"] < train_cut]
    val = df[(df["date"] >= train_cut) & (df["date"] < val_cut)]
    test = df[df["date"] >= val_cut]
    return train, val, test


def train():
    df = build_dataset()
    train, val, test = _time_split(df)

    Xtr, ytr = train[FEATURE_COLS], train["label"]
    Xva, yva = val[FEATURE_COLS], val["label"]
    Xte, yte = test[FEATURE_COLS], test["label"]

    model = Pipeline([
        ("scale", StandardScaler()),
        ("gb", GradientBoostingClassifier(
            n_estimators=120, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42)),
    ])
    model.fit(Xtr, ytr)

    def evaluate(X, y, name):
        if len(np.unique(y)) < 2:
            return {"split": name, "n": int(len(y)), "note": "single-class split"}
        p = model.predict_proba(X)[:, 1]
        return {
            "split": name,
            "n": int(len(y)),
            "base_rate": round(float(y.mean()), 3),
            "accuracy": round(accuracy_score(y, (p > 0.5).astype(int)), 3),
            "auc": round(roc_auc_score(y, p), 3),
            "brier": round(brier_score_loss(y, p), 3),  # calibration; lower better
        }

    metrics = {
        "model": "GradientBoostingClassifier",
        "features": FEATURE_COLS,
        "split": "time-ordered 60/20/20 (no lookahead)",
        "train": evaluate(Xtr, ytr, "train"),
        "validation": evaluate(Xva, yva, "validation"),
        "test": evaluate(Xte, yte, "test"),
        "feature_importance": dict(zip(
            FEATURE_COLS,
            [round(float(v), 3) for v in model.named_steps["gb"].feature_importances_])),
        "honest_caveats": [
            "Predicts relative (vs-sector) direction, not magnitude or price.",
            "Synthetic demo data has no real alpha; expect AUC near 0.5 on it.",
            "On real data, transaction costs and capacity are NOT modeled here.",
        ],
    }

    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    return metrics


def load():
    if not MODEL_PATH.exists():
        train()
    return joblib.load(MODEL_PATH)


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    m = train()
    print(json.dumps(m, indent=2))
