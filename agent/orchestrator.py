"""
Agent orchestrator (Phase 4) — the planning loop, written by hand.

Flow:
  1. receive the question
  2. extract the target ticker(s)
  3. PLAN: produce an ordered list of tool calls (rule-based here; an LLM planner
     is a drop-in upgrade — see plan_with_llm)
  4. EXECUTE each tool, storing results in working memory
  5. decide whether enough evidence is gathered
  6. COMPOSE the final cited thesis (numbers from memory, words from llm.py)

Deliberately transparent: it records each step so the frontend / CLI can show
the agent "thinking". This is the visually impressive part of the demo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from data_pipeline.db import connect
from agent import llm
from agent.tools import REGISTRY


@dataclass
class AgentRun:
    question: str
    ticker: str
    plan: list = field(default_factory=list)
    steps: list = field(default_factory=list)   # [{tool, args, result_summary}]
    memory: dict = field(default_factory=dict)
    thesis: str = ""


def _known_tickers() -> list[str]:
    with connect() as conn:
        return [r["ticker"] for r in conn.execute("SELECT ticker FROM companies").fetchall()]


def extract_ticker(question: str) -> str | None:
    known = _known_tickers()
    # explicit symbol match first
    for tok in re.findall(r"[A-Z]{2,5}", question):
        if tok in known:
            return tok
    # name fallback
    with connect() as conn:
        for t in known:
            name = conn.execute("SELECT name FROM companies WHERE ticker=?", (t,)).fetchone()["name"]
            if name.split()[0].lower() in question.lower():
                return t
    return known[0] if known else None


def make_plan(question: str, ticker: str) -> list[dict]:
    """Rule-based planner. Always values + scores; adds risk if the question
    mentions risk/downside; adds a screen if it mentions peers/screen/cheap."""
    q = question.lower()
    plan = [
        {"tool": "fundamentals", "args": {"ticker": ticker}},
        {"tool": "valuation", "args": {"ticker": ticker}},
        {"tool": "ml_score", "args": {"ticker": ticker}},
    ]
    if any(w in q for w in ["risk", "downside", "var", "volatil", "drawdown"]):
        peers = _peer_basket(ticker)
        plan.append({"tool": "risk", "args": {"tickers": peers}})
    else:
        plan.append({"tool": "risk", "args": {"tickers": [ticker]}})
    if any(w in q for w in ["peer", "screen", "cheap", "vs ", "versus", "compare"]):
        plan.insert(1, {"tool": "screen", "args": {"sector": _sector_of(ticker)}})
    return plan


def _sector_of(ticker: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT sector FROM companies WHERE ticker=?", (ticker,)).fetchone()
    return row["sector"] if row else None


def _peer_basket(ticker: str, k: int = 4) -> list[str]:
    sector = _sector_of(ticker)
    with connect() as conn:
        peers = [r["ticker"] for r in conn.execute(
            "SELECT ticker FROM companies WHERE sector=? LIMIT ?", (sector, k)).fetchall()]
    if ticker not in peers:
        peers = [ticker] + peers[:k - 1]
    return peers


def plan_with_llm(question: str, ticker: str) -> list[dict]:
    """Use the LLM planner if a key is set and it returns a valid plan;
    otherwise fall back to the deterministic rule-based plan. The LLM only
    picks/orders tools — it is validated against the registry in planner.py."""
    from agent.planner import llm_plan
    peers = _peer_basket(ticker)
    plan = llm_plan(question, ticker, peers)
    return plan if plan else make_plan(question, ticker)


def run(question: str, use_llm_planner: bool = False) -> AgentRun:
    ticker = extract_ticker(question)
    if ticker is None:
        raise ValueError("No known ticker found in question or universe is empty.")

    plan = plan_with_llm(question, ticker) if use_llm_planner else make_plan(question, ticker)
    run_obj = AgentRun(question=question, ticker=ticker, plan=plan)

    for step in plan:
        fn, _desc = REGISTRY[step["tool"]]
        result = fn(**step["args"])
        run_obj.memory[step["tool"]] = result
        run_obj.steps.append({
            "tool": step["tool"],
            "args": step["args"],
            "summary": _summarize(step["tool"], result),
        })

    run_obj.thesis = llm.compose_thesis(question, ticker, run_obj.memory)
    _persist(run_obj)
    return run_obj


def _summarize(tool: str, result: dict) -> str:
    if tool == "valuation":
        return f"DCF fair value ${result.get('dcf_fair_value')} ({result.get('dcf_upside_pct')}%)"
    if tool == "risk":
        return f"95% VaR {result.get('VaR_pct')}%"
    if tool == "ml_score":
        return f"P(outperform)={result.get('p_outperform_sector_1m')}"
    if tool == "fundamentals":
        return f"ROIC {result.get('roic_pct')}%, EV/EBITDA {result.get('ev_ebitda')}"
    if tool == "screen":
        return f"{len(result.get('matches', []))} matches"
    return "ok"


def _persist(run_obj: AgentRun) -> None:
    with connect() as conn:
        rid = conn.insert_returning_id("INSERT INTO runs(question) VALUES (?)",
                                       (run_obj.question,))
        conn.execute("INSERT INTO theses(run_id, ticker, body) VALUES (?,?,?)",
                     (rid, run_obj.ticker, run_obj.thesis))


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    r = run("Is NVDA overvalued vs its semiconductor peers given the downside risk?")
    print("PLAN:", [s["tool"] for s in r.steps])
    for s in r.steps:
        print(f"  - {s['tool']}: {s['summary']}")
    print("\n" + r.thesis)
