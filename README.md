# AlphaForge

**An agentic equity-research & portfolio-risk workbench.** Ask a plain-English
question — *"Is NVDA overvalued vs its semiconductor peers given the downside
risk?"* — and an agent plans a multi-step workflow: pull fundamentals, screen
peers, run a DCF + comparables valuation, score a trained ML model, simulate
Monte-Carlo VaR, and write a **cited** investment thesis.

The one design rule everything is built around:

> **Numbers come from code. Words come from the LLM. The LLM never invents a number.**

---

## Quick start (≈2 minutes, no API keys, runs offline)

```bash
# 1. clone / unzip, then from the project root:
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. run the whole pipeline end to end
python run_demo.py
```

That's it. `run_demo.py` builds a dataset, trains the ML model, runs the agent,
and prints a cited thesis. No keys, no database server, no network needed — it
ships with a deterministic synthetic dataset for the AI-compute universe
(NVDA, AMD, AVGO, TSM, ASML, MU, INTC, plus a few software names).

Try other questions:
```bash
python run_demo.py --question "Is AMD cheap vs its peers?"
python run_demo.py --question "What is the downside risk in TSM?"
```

### Interactive UI
```bash
uvicorn api.main:app --reload          # starts the API on :8000
# then open frontend/index.html in your browser
```
You'll see the agent's plan stream in step-by-step, then the thesis.

---

## Opening this in VS Code
1. **File → Open Folder…** and pick the `alphaforge` folder.
2. Open a terminal (**Ctrl+`**) and run the Quick-start commands above.
3. Select the `.venv` interpreter when VS Code prompts (bottom-right, or
   *Python: Select Interpreter*).
4. Recommended extensions: **Python**, **Pylance**. Press ▶ on `run_demo.py`.

---

## What's real here (and what's a deliberate simplification)
| Area | What it does | Note |
|---|---|---|
| Data pipeline | fetch → clean → validate → store, graceful failure | SQLite default; `--live` pulls **real yfinance prices + fundamentals**, `--edgar` adds **SEC EDGAR** |
| Database | dual backend | SQLite (zero-setup) **or Postgres** via `DATABASE_URL` |
| Cache | caches expensive sims | **Redis** via `REDIS_URL`, else in-memory fallback |
| ML model | GBM predicting P(beat sector next month), **time-aware split** | honest metrics incl. where it fails |
| Deep learning | optional LSTM volatility forecaster (PyTorch) | `models/lstm_vol.py` |
| Valuation | DCF + comparables + WACC×growth sensitivity grid | all formulas in `finance/valuation.py` |
| Risk | Monte-Carlo VaR/CVaR, correlated draws | Python always; C++ core optional |
| Agent | hand-written plan→execute→compose loop | `agent/orchestrator.py` |
| LLM planner | LLM picks/orders tools, **validated** against the registry | `agent/planner.py`; rule-based fallback |
| Automation | **nightly scheduler**: refresh → retrain → daily brief → **threshold alerts** | `scheduler/`, APScheduler + email/console |
| API + UI | FastAPI + a single-file frontend | no npm needed |
| BI | **Excel + CSV export** for Tableau/Power BI + dashboard spec | `bi/export.py`, `bi/DASHBOARD_SPEC.md` |
| Infra | **Docker Compose** (app + Postgres + Redis + scheduler), **GitHub Actions CI**, Render deploy | `Dockerfile`, `docker-compose.yml`, `.github/`, `render.yaml` |

## The parts a reviewer should look at first
- **Time-aware train/test split** — `models/train_classifier.py`. On the
  signal-free synthetic data, train AUC ≈ 0.80 but test AUC ≈ 0.49. That gap is
  the **anti-leakage harness working**, not a bug. Swap in real data via `--live`
  to test for actual signal.
- **C++ vs Python benchmark** — `python -m risk.benchmark`. Shows C++ ≈ 18× a
  naive Python loop and ≈ par with NumPy (which is already vectorized C). The
  honest takeaway: C++ wins when the path logic can't be vectorized.
- **"Numbers from code, words from the LLM"** — `agent/llm.py` is handed
  pre-computed evidence as JSON and instructed to use only those numbers; the
  thesis cites each figure's source tool.
- **`ARCHITECTURE.md`** and **`docs/PRODUCT_BRIEF.md`** — the reasoning in plain words.
- **`notebooks/eda.ipynb`** — exploratory analysis with charts and written takeaways,
  including the time-aware-validation chart that visualizes the leakage check.

## Enabling the optional pieces
```bash
# Live market data (real prices + fundamentals) instead of synthetic:
pip install yfinance
python run_demo.py --live                       # yfinance prices + fundamentals
python -m data_pipeline.ingest --live --edgar   # also cross-check via SEC EDGAR
#   (for --edgar, set SEC_USER_AGENT="Your Name you@email.com")

# LLM-written prose AND an LLM planner (otherwise rule-based + template composer):
pip install anthropic
export ANTHROPIC_API_KEY=sk-...                 # Windows: set ANTHROPIC_API_KEY=...
python run_demo.py --llm-planner

# Postgres + Redis instead of SQLite + in-memory cache:
pip install "psycopg[binary]" redis
export DATABASE_URL=postgresql://user:pass@localhost:5432/alphaforge
export REDIS_URL=redis://localhost:6379/0

# Nightly automation (refresh -> retrain -> daily brief -> alerts):
python -m scheduler.jobs --once                 # run the job right now
python -m scheduler.jobs --serve                # daily at 06:30 (blocking)
#   alerts email if SMTP_* env is set, otherwise print + store in the DB

# BI artifact for Tableau / Power BI:
python -m bi.export                             # -> bi/output/alphaforge_bi.xlsx + CSVs
#   then connect Tableau/Power BI and follow bi/DASHBOARD_SPEC.md

# C++ risk engine (~18x over a naive loop):
pip install pybind11 && pip install ./risk/cpp
python -m risk.benchmark

# Deep-learning vol model:
pip install torch && python -m models.lstm_vol
```

## Run the whole stack with Docker (Postgres + Redis + API + scheduler)
```bash
docker compose up --build
# API on http://localhost:8000 (open frontend/index.html), Postgres on :5432, Redis on :6379
```

## Tests
```bash
pytest -q
```

## Project layout
```
data_pipeline/   ingestion (yfinance + SEC EDGAR), dual-backend DB, Redis cache, synthetic generator
models/          features, time-aware GBM classifier, optional LSTM
finance/         DCF + comparables valuation, factor analysis & screener
risk/            Monte-Carlo VaR (Python) + C++ pybind11 core + benchmark
agent/           orchestrator (plan→execute→compose), tools, LLM planner + prose
scheduler/       nightly job (refresh/retrain/brief) + threshold alert engine
api/             FastAPI backend (ask, valuation, risk, alerts, runs, data health)
frontend/        single-file UI (no build step)
bi/              Excel/CSV export + Tableau/Power BI dashboard spec
notebooks/       eda.ipynb (executed, charts render on GitHub) + eda.py (CI-friendly script)
docs/            product brief + AI-compute equity-research note
tests/           valuation, risk, cache, alerts, ingestion tests
Dockerfile, docker-compose.yml, .github/workflows/ci.yml, render.yaml
```

## What I'd still do with more time
- Real quarterly fundamentals history (not just TTM) and a point-in-time store.
- An OMS/portfolio layer so VaR runs on actual positions and weights.
- Backtest harness with transaction costs to validate the ML signal on real data.
- Publish the Tableau dashboard to Tableau Public as a live linked artifact.

---
*Built as a portfolio project. Data in the default mode is synthetic and for
demonstration only; nothing here is investment advice.*
