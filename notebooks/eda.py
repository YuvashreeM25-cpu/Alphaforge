"""
Exploratory analysis (Phase 2) — run as a script or paste into a Jupyter cell.

    python notebooks/eda.py

Produces: return correlations across the universe, sector vol comparison, and
the factor table — with printed takeaways. (Kept as a script so it runs in CI
without a notebook kernel; convert to .ipynb if you prefer.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data_pipeline.db import connect
from data_pipeline.sample_data import generate
from finance.factors import factor_table


def main():
    from data_pipeline.db import init_db
    init_db()
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM prices").fetchone()["c"]
    if not n:
        generate()

    with connect() as conn:
        px = conn.read_df("SELECT ticker,date,close FROM prices")
    px["date"] = pd.to_datetime(px["date"])
    wide = px.pivot(index="date", columns="ticker", values="close").sort_index()
    rets = np.log(wide).diff().dropna()

    print("=== Return correlation matrix ===")
    corr = rets.corr().round(2)
    print(corr.to_string())
    print("\nTakeaway: within-sector names co-move; that correlation is exactly what")
    print("the VaR engine's covariance/Cholesky step captures (diversification is real).")

    print("\n=== Annualized volatility by ticker ===")
    vol = (rets.std() * np.sqrt(252) * 100).round(1).sort_values(ascending=False)
    print(vol.to_string())

    print("\n=== Factor table (valuation / quality / leverage) ===")
    ft = pd.DataFrame(factor_table())
    print(ft.to_string(index=False))
    print("\nTakeaway: rank on ROIC and EV/EBITDA together — cheap + high-quality is")
    print("the classic value-quality screen the agent's `screen` tool exposes.")


if __name__ == "__main__":
    main()
