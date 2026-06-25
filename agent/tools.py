"""
Tool registry (Phase 4).

Each function here is a TOOL the agent can call. Every tool returns structured
numbers computed by our own code. The LLM never produces these — it only gets to
describe them. This is the "numbers from code, words from the LLM" boundary that
separates this from a chatbot.
"""
from __future__ import annotations

from data_pipeline.cache import cached
from finance import factors, valuation
from models.predict import predict_latest
from risk.montecarlo_var import monte_carlo_var


def tool_fundamentals(ticker: str) -> dict:
    rows = [r for r in factors.factor_table() if r["ticker"] == ticker.upper()]
    return rows[0] if rows else {"ticker": ticker, "error": "not found"}


def tool_screen(max_ev_ebitda=None, min_roic=None, sector=None) -> dict:
    return {"matches": factors.screen(max_ev_ebitda, min_roic, sector)}


def tool_valuation(ticker: str) -> dict:
    d = valuation.dcf(ticker.upper())
    comps = valuation.comparables(ticker.upper())
    return {
        "dcf_fair_value": d.fair_value_per_share,
        "dcf_upside_pct": d.upside_pct,
        "current_price": d.current_price,
        "dcf_assumptions": d.assumptions,
        "sensitivity": d.sensitivity,
        "comparables": comps,
    }


def tool_ml_score(ticker: str) -> dict:
    return predict_latest(ticker.upper())


@cached("risk")
def tool_risk(tickers, weights=None) -> dict:
    return monte_carlo_var(tickers, weights=weights, n_paths=100_000)


# name -> (callable, human description) used by the planner
REGISTRY = {
    "fundamentals": (tool_fundamentals, "Valuation/quality/leverage factors for one ticker"),
    "screen": (tool_screen, "Filter the universe by EV/EBITDA, ROIC, sector"),
    "valuation": (tool_valuation, "DCF + comparables fair value and sensitivity"),
    "ml_score": (tool_ml_score, "Model probability the stock beats its sector next month"),
    "risk": (tool_risk, "Monte-Carlo VaR/CVaR for a portfolio of tickers"),
}
