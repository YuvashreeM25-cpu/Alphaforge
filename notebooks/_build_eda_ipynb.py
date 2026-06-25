"""
Builds notebooks/eda.ipynb (markdown + code) and executes it so the charts are
embedded as outputs (renders on GitHub without anyone running it).

Run:  python notebooks/_build_eda_ipynb.py
"""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
OUT = HERE / "eda.ipynb"

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = []

cells.append(md(
    "# AlphaForge — Exploratory Data Analysis\n\n"
    "Phase-2 analytics for the AI-compute equity universe. The goal of this "
    "notebook is not just charts — it is to show the *reasoning* that the rest "
    "of AlphaForge is built on:\n\n"
    "1. how the names co-move (and why that feeds the VaR engine),\n"
    "2. their risk and quality/value factor structure, and\n"
    "3. the **time-aware validation** discipline that keeps the ML model honest.\n\n"
    "_Default data is synthetic and reproducible; run `python -m data_pipeline.ingest "
    "--live` first to analyse real market data instead._"
))

cells.append(code(
    "%matplotlib inline\n"
    "import sys, pathlib\n"
    "sys.path.insert(0, str(pathlib.Path.cwd().parent))  # project root\n"
    "import numpy as np, pandas as pd, matplotlib.pyplot as plt\n"
    "plt.rcParams['figure.figsize'] = (8, 4.5); plt.rcParams['axes.grid'] = True\n"
    "from data_pipeline.db import init_db, connect\n"
    "from data_pipeline.sample_data import generate\n"
    "init_db()\n"
    "with connect() as c:\n"
    "    n = c.execute('SELECT COUNT(*) AS x FROM prices').fetchone()['x']\n"
    "if not n:\n"
    "    generate()\n"
    "with connect() as c:\n"
    "    px = c.read_df('SELECT ticker,date,close FROM prices')\n"
    "    comp = c.read_df('SELECT ticker,sector FROM companies')\n"
    "px['date'] = pd.to_datetime(px['date'])\n"
    "wide = px.pivot(index='date', columns='ticker', values='close').sort_index()\n"
    "rets = np.log(wide).diff().dropna()\n"
    "print('universe:', list(wide.columns))\n"
    "print('trading days:', len(wide), '| return obs:', len(rets))"
))

cells.append(md(
    "## 1. How do the names co-move?\n\n"
    "Correlation of daily log-returns. This is the matrix the risk engine "
    "decomposes (Cholesky) to draw correlated paths — co-movement is exactly "
    "what makes diversification *quantifiable*."
))
cells.append(code(
    "corr = rets.corr()\n"
    "fig, ax = plt.subplots(figsize=(6.5, 5.5))\n"
    "im = ax.imshow(corr, vmin=-1, vmax=1, cmap='RdBu_r')\n"
    "ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=90)\n"
    "ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.columns)\n"
    "for i in range(len(corr)):\n"
    "    for j in range(len(corr)):\n"
    "        ax.text(j, i, f'{corr.iloc[i,j]:.2f}', ha='center', va='center', fontsize=7)\n"
    "fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)\n"
    "ax.set_title('Daily return correlation'); ax.grid(False); plt.tight_layout(); plt.show()"
))
cells.append(md(
    "**Takeaway.** Names inside a sector co-move more than across sectors. That "
    "positive within-sector correlation is why an equal-weight semis basket's VaR "
    "is *higher* than diversifying across sectors would imply — and why the risk "
    "engine must model the full covariance, not just per-name volatility."
))

cells.append(md(
    "## 2. Risk: annualized volatility\n\n"
    "Daily return std scaled by √252. The dispersion here is the raw material for "
    "position sizing and the VaR simulation."
))
cells.append(code(
    "vol = (rets.std() * np.sqrt(252) * 100).sort_values(ascending=False)\n"
    "ax = vol.plot(kind='bar')\n"
    "ax.set_ylabel('Annualized vol (%)'); ax.set_title('Volatility by ticker')\n"
    "plt.tight_layout(); plt.show()\n"
    "vol.round(1).to_frame('ann_vol_%')"
))
cells.append(md(
    "**Takeaway.** The high-vol names dominate any equal-weight book's risk "
    "budget; this is the argument for risk-weighting rather than equal-weighting, "
    "and it is what the alert engine watches via the 95% VaR threshold."
))

cells.append(md(
    "## 3. Value vs quality (the screen the agent automates)\n\n"
    "Each name plotted by valuation (EV/EBITDA, x) against quality (ROIC, y), "
    "sized by market cap and colored by DCF upside. The **top-left** quadrant — "
    "cheap *and* high-quality — is the classic value-quality screen."
))
cells.append(code(
    "from finance.factors import factor_table\n"
    "from finance.valuation import dcf\n"
    "rows = factor_table()\n"
    "df = pd.DataFrame(rows)\n"
    "df['dcf_upside'] = [dcf(t).upside_pct for t in df['ticker']]\n"
    "sub = df.dropna(subset=['ev_ebitda','roic_pct'])\n"
    "fig, ax = plt.subplots()\n"
    "sizes = (sub['market_cap'] / sub['market_cap'].max() * 600 + 40)\n"
    "sc = ax.scatter(sub['ev_ebitda'], sub['roic_pct'], s=sizes,\n"
    "                c=sub['dcf_upside'], cmap='RdYlGn', edgecolor='k', alpha=0.85)\n"
    "for _, r in sub.iterrows():\n"
    "    ax.annotate(r['ticker'], (r['ev_ebitda'], r['roic_pct']),\n"
    "                fontsize=8, xytext=(4,4), textcoords='offset points')\n"
    "ax.set_xlabel('EV/EBITDA (x)  — cheaper is left'); ax.set_ylabel('ROIC (%)  — better is up')\n"
    "ax.set_title('Value vs quality (color = DCF upside %)')\n"
    "fig.colorbar(sc, ax=ax, label='DCF upside %'); plt.tight_layout(); plt.show()\n"
    "df[['ticker','sector','ev_ebitda','roic_pct','dcf_upside']].round(1)"
))
cells.append(md(
    "**Takeaway.** This single view is what `screen` + `valuation` automate inside "
    "the agent: rank on cheapness and quality jointly, then let the DCF flag which "
    "of the high-quality names still offer upside."
))

cells.append(md(
    "## 4. The credibility check: time-aware validation\n\n"
    "The most important chart in the project. We train the GBM classifier and "
    "compare AUC across a **time-ordered** train/validation/test split. If a "
    "model shows strong train AUC but its out-of-sample AUC collapses toward "
    "0.5, that is the signal there is no real edge — and it is exactly what a "
    "leakage-free split is supposed to expose. (On synthetic data there is no "
    "alpha by construction, so this *should* happen.)"
))
cells.append(code(
    "from models.train_classifier import train\n"
    "m = train()\n"
    "splits = ['train','validation','test']\n"
    "aucs = [m[s].get('auc', float('nan')) for s in splits]\n"
    "ax = plt.subplot()\n"
    "bars = ax.bar(splits, aucs)\n"
    "ax.axhline(0.5, linestyle='--', label='coin-flip (0.5)')\n"
    "for b, a in zip(bars, aucs):\n"
    "    ax.text(b.get_x()+b.get_width()/2, a+0.01, f'{a:.2f}', ha='center')\n"
    "ax.set_ylim(0, 1); ax.set_ylabel('AUC'); ax.legend()\n"
    "ax.set_title('AUC by split (time-ordered, no lookahead)')\n"
    "plt.tight_layout(); plt.show()\n"
    "pd.DataFrame({s: m[s] for s in splits}).T[['n','base_rate','auc','accuracy']]"
))
cells.append(md(
    "**Takeaway.** Train AUC ≫ test AUC here is the validation harness *working*. "
    "A naive random split would have leaked overlapping-window information across "
    "the boundary and reported a flatteringly high test score — the classic "
    "finance-ML trap. Swap in real data (`--live`) to test for genuine signal; "
    "the honest expectation is that it is small and hard-won."
))

cells.append(md(
    "## Conclusions\n\n"
    "- The universe co-moves within sectors → diversification is real and the VaR "
    "engine models it via the return covariance.\n"
    "- Volatility dispersion argues for risk-weighting, which the alert engine "
    "monitors.\n"
    "- A joint value–quality screen, confirmed by a DCF, is the core idea the "
    "agent automates.\n"
    "- A time-aware split keeps the ML claims honest — the single most important "
    "discipline in finance ML, and the thing a reviewer should check first."
))

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
    "language_info": {"name": "python"},
})

print("executing notebook...")
client = NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(HERE)}})
client.execute()
nbf.write(nb, OUT)
print(f"wrote {OUT}")
