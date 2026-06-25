"""
VaR benchmark (Phase 3 deliverable) — an HONEST three-way comparison.

We time the SAME Monte-Carlo VaR three ways:
  1) naive pure-Python loop  (what a tight path-by-path loop really costs)
  2) NumPy-vectorized Python (already calls into C under the hood)
  3) C++ via pybind11

The senior point this makes: NumPy is already vectorized C, so it beats the
naive loop massively and runs neck-and-neck with C++ for THIS vectorizable
problem. C++ earns its place when the path logic CANNOT be vectorized —
path-dependent payoffs, early-exercise, barrier checks — where you're forced
back into a per-step loop and Python's interpreter overhead dominates. Knowing
that distinction is the actual signal.

Run:  python -m risk.benchmark
"""
from __future__ import annotations

import time

import numpy as np

from data_pipeline.db import connect
from risk.montecarlo_var import _returns_matrix, monte_carlo_var


def _naive_python_var(mu, L, w, n_assets, n_paths, confidence, seed):
    """Deliberately un-vectorized, to show the cost C++ actually removes."""
    import random
    rng = random.Random(seed)
    losses = []
    for _ in range(n_paths):
        z = [rng.gauss(0, 1) for _ in range(n_assets)]
        port = 0.0
        for i in range(n_assets):
            acc = 0.0
            for j in range(i + 1):
                acc += L[i][j] * z[j]
            port += w[i] * (mu[i] + acc)
        losses.append(-port)
    losses.sort()
    idx = int(confidence * (len(losses) - 1))
    return losses[idx]


def _inputs(tickers):
    rets, used = _returns_matrix(tickers)
    mu = rets.mean(axis=0)
    cov = np.cov(rets, rowvar=False)
    L = np.linalg.cholesky(cov + 1e-12 * np.eye(len(used)))
    w = np.ones(len(used)) / len(used)
    return mu, L, w, used


def main(n_paths=300_000):
    from data_pipeline.sample_data import generate
    with connect() as conn:
        has = conn.execute("SELECT COUNT(*) c FROM prices").fetchone()["c"]
    if not has:
        generate()

    tickers = ["NVDA", "AMD", "TSM", "ASML"]
    mu, L, w, used = _inputs(tickers)

    # 1) naive pure-Python loop (smaller path count — it's slow on purpose)
    naive_paths = max(20_000, n_paths // 15)
    t0 = time.perf_counter()
    naive_var = _naive_python_var(mu.tolist(), L.tolist(), w.tolist(),
                                  len(used), naive_paths, 0.95, 7)
    naive_t = time.perf_counter() - t0
    naive_norm = naive_t / naive_paths * n_paths  # scale to common path count
    print(f"Naive Python loop  VaR {naive_var*100:.3f}%   "
          f"({naive_t:.3f}s @ {naive_paths:,} paths -> ~{naive_norm:.2f}s @ {n_paths:,})")

    # 2) NumPy-vectorized Python
    t0 = time.perf_counter()
    py = monte_carlo_var(tickers, n_paths=n_paths, seed=7)
    py_t = time.perf_counter() - t0
    print(f"NumPy vectorized   VaR {py['VaR_pct']:.3f}%   ({py_t:.3f}s @ {n_paths:,} paths)")

    # 3) C++
    try:
        import var_engine
    except ImportError:
        print("\nC++ module not built. To enable it:")
        print("    pip install pybind11")
        print("    pip install ./risk/cpp")
        print("Then re-run:  python -m risk.benchmark")
        print(f"\n(So far: NumPy is ~{naive_norm/py_t:.0f}x faster than the naive loop.)")
        return

    t0 = time.perf_counter()
    var, cvar = var_engine.mc_var(
        mu.tolist(), L.flatten().tolist(), w.tolist(),
        len(used), n_paths, 1, 0.95, 7)
    cpp_t = time.perf_counter() - t0
    print(f"C++ pybind11       VaR {var*100:.3f}%   ({cpp_t:.3f}s @ {n_paths:,} paths)")

    print("\n--- speedups (normalized to "
          f"{n_paths:,} paths) ---")
    print(f"  C++   vs naive Python : {naive_norm / cpp_t:6.1f}x")
    print(f"  C++   vs NumPy        : {py_t / cpp_t:6.1f}x")
    print(f"  NumPy vs naive Python : {naive_norm / py_t:6.1f}x")
    print("\nTakeaway: NumPy already buys most of the speed because it IS C. "
          "C++ pulls ahead when the path logic can't be vectorized.")


if __name__ == "__main__":
    main()
