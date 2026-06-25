"""
FastAPI backend (Phase 5).

Endpoints:
  GET  /health
  GET  /universe                      -> tickers in the DB
  GET  /factors                       -> factor table for the dashboard
  POST /ask        {question}         -> runs the agent, returns plan+steps+thesis
  GET  /valuation/{ticker}
  POST /risk       {tickers, weights} -> Monte-Carlo VaR

Run:  uvicorn api.main:app --reload
Then open frontend/index.html (it points at http://localhost:8000).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.orchestrator import run as run_agent
from data_pipeline.db import connect
from finance import factors, valuation
from risk.montecarlo_var import monte_carlo_var

app = FastAPI(title="AlphaForge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    use_llm_planner: bool = False


class RiskRequest(BaseModel):
    tickers: list[str]
    weights: list[float] | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe():
    with connect() as conn:
        rows = conn.execute("SELECT ticker, name, sector FROM companies ORDER BY ticker").fetchall()
    return [dict(r) for r in rows]


@app.get("/factors")
def factor_table():
    return factors.factor_table()


@app.get("/valuation/{ticker}")
def get_valuation(ticker: str):
    d = valuation.dcf(ticker.upper())
    return {
        "ticker": ticker.upper(),
        "dcf_fair_value": d.fair_value_per_share,
        "upside_pct": d.upside_pct,
        "current_price": d.current_price,
        "assumptions": d.assumptions,
        "sensitivity": d.sensitivity,
        "comparables": valuation.comparables(ticker.upper()),
    }


@app.post("/risk")
def post_risk(req: RiskRequest):
    return monte_carlo_var(req.tickers, weights=req.weights, n_paths=100_000)


@app.post("/ask")
def ask(req: AskRequest):
    r = run_agent(req.question, use_llm_planner=req.use_llm_planner)
    return {
        "question": r.question,
        "ticker": r.ticker,
        "plan": [s["tool"] for s in r.steps],
        "steps": r.steps,
        "thesis": r.thesis,
    }


@app.get("/alerts")
def get_alerts(limit: int = 50):
    with connect() as conn:
        rows = conn.execute(
            "SELECT fired_at, ticker, rule, value, message FROM alerts "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/runs")
def get_runs(limit: int = 20):
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.id, r.question, r.created_at, t.ticker "
            "FROM runs r LEFT JOIN theses t ON t.run_id = r.id "
            "ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/health/data")
def data_health():
    """Latest ingestion result + row counts — useful for the scheduler dashboard."""
    with connect() as conn:
        last = conn.execute(
            "SELECT run_at, source, ok, failed FROM ingest_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prices = conn.execute("SELECT COUNT(*) c FROM prices").fetchone()["c"]
        names = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
    return {"last_ingest": dict(last) if last else None,
            "price_rows": prices, "companies": names, "backend": __import__(
                "data_pipeline.db", fromlist=["backend"]).backend()}
