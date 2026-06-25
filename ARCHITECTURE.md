# Architecture

AlphaForge answers a plain-English research question by *planning and executing a
multi-step workflow*. The design rule that matters most:

> **Numbers come from code. Words come from the LLM. The LLM never invents a number.**

## Request flow

```
  user question
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│  AGENT ORCHESTRATOR  (agent/orchestrator.py)                  │
│   1. extract ticker(s)                                        │
│   2. PLAN  → ordered list of tool calls                       │
│   3. EXECUTE tools, store results in working memory           │
│   4. COMPOSE thesis from memory (agent/llm.py)                │
└──────────────────────────────────────────────────────────────┘
      │ calls tools (agent/tools.py)
      ├── fundamentals → finance/factors.py
      ├── screen       → finance/factors.py
      ├── valuation    → finance/valuation.py     (DCF + comparables)
      ├── ml_score     → models/predict.py         (trained GBM)
      └── risk         → risk/montecarlo_var.py     (C++ core optional)
      │
      ▼
   SQLite (data_pipeline/db.py)  ← populated by data_pipeline/ingest.py
```

## Why each piece is where it is
- **Dual-backend data layer:** SQLite by default (zero-setup so the repo runs on
  clone); set `DATABASE_URL` to switch to Postgres. A thin adapter (`data_pipeline/db.py`)
  rewrites `?`→`%s`, handles `RETURNING`/`AUTOINCREMENT`, and exposes dialect-aware
  `upsert`, so application code never branches on backend.
- **Live ingestion:** `data_pipeline/ingest.py` pulls real prices and fundamentals
  from yfinance, with `data_pipeline/edgar.py` cross-checking fundamentals against
  the SEC EDGAR companyfacts API. Every ticker fails independently and is logged.
- **Redis cache with fallback:** `data_pipeline/cache.py` memoizes expensive sims
  (e.g. VaR); if `REDIS_URL` is unreachable it silently uses an in-memory dict.
- **ML model trained locally with a TIME-AWARE split:** a random split leaks the
  future into the past in finance data. On the signal-free synthetic data this
  correctly shows train AUC ≫ test AUC — the leakage check *working*.
- **Risk in C++ via pybind11 (optional):** `risk/benchmark.py` shows C++ ≈ 18× a
  naive Python loop and ≈ par with NumPy (already vectorized C). The honest lesson:
  C++ earns its place when the path logic can't be vectorized.
- **LLM as planner + narrator, never the brain:** `agent/planner.py` lets the LLM
  *choose and order tools*, but the plan is validated against the registry before
  it runs. `agent/llm.py` turns the computed evidence into prose with an
  instruction to use *only* the supplied numbers. With no API key, both fall back
  to deterministic logic — still sourced, still no invented numbers.
- **Automation:** `scheduler/jobs.py` (APScheduler) refreshes data, retrains the
  model, runs the agent across a watchlist for a daily brief, and `scheduler/alerts.py`
  fires threshold breaches (VaR / DCF downside) by email or console.

## The boundary that makes this not-a-chatbot
Every figure in a thesis is traceable to the tool that produced it (the prose
cites `(valuation)`, `(risk)`, etc.). The LLM cannot reach the database or the
math; it only sees the structured results the orchestrator chose to give it, and
even as planner it can only pick from a validated tool registry.
