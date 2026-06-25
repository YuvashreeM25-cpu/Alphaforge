"""
LLM planner (Phase 4 upgrade).

Asks the LLM to choose an ordered list of tool calls for a question. The output
is STRICTLY VALIDATED against the tool registry before use: unknown tools,
bad argument names, or malformed JSON all trigger a fall back to the
deterministic rule-based planner. The LLM influences *which* tools run and in
what order — it still never produces a number.

No ANTHROPIC_API_KEY -> rule-based planner is used directly.
"""
from __future__ import annotations

import json
import os

from agent.tools import REGISTRY

MODEL = os.environ.get("ALPHAFORGE_LLM_MODEL", "claude-sonnet-4-6")

# allowed argument names per tool (validation whitelist)
_ARG_SCHEMA = {
    "fundamentals": {"ticker"},
    "screen": {"max_ev_ebitda", "min_roic", "sector"},
    "valuation": {"ticker"},
    "ml_score": {"ticker"},
    "risk": {"tickers", "weights"},
}


def _tool_catalog() -> str:
    return "\n".join(f"- {name}({', '.join(sorted(_ARG_SCHEMA[name]))}): {desc}"
                     for name, (_fn, desc) in REGISTRY.items())


def _validate(plan, ticker, peer_basket):
    """Keep only well-formed steps; coerce obvious arg shapes."""
    clean = []
    for step in plan:
        tool = step.get("tool")
        if tool not in REGISTRY:
            continue
        args = step.get("args", {}) or {}
        args = {k: v for k, v in args.items() if k in _ARG_SCHEMA[tool]}
        # fill required ticker/tickers if the LLM omitted them
        if tool in ("fundamentals", "valuation", "ml_score") and "ticker" not in args:
            args["ticker"] = ticker
        if tool == "risk" and "tickers" not in args:
            args["tickers"] = peer_basket
        clean.append({"tool": tool, "args": args})
    return clean


def llm_plan(question: str, ticker: str, peer_basket: list[str]) -> list[dict] | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None

    system = (
        "You are the planner for an equity-research agent. Given a question, "
        "output ONLY a JSON array of tool calls to run, in order. Each item is "
        '{"tool": <name>, "args": {...}}. Use only these tools:\n'
        f"{_tool_catalog()}\n"
        "Rules: always include valuation and ml_score for the target ticker; "
        "include risk (with a peer basket) when the question mentions risk or "
        "downside; include screen when it mentions peers/cheap/compare. "
        "Output JSON only, no prose."
    )
    user = f"Question: {question}\nTarget ticker: {ticker}\nPeer basket: {peer_basket}"
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=MODEL, max_tokens=500, system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        plan = json.loads(text)
        if not isinstance(plan, list) or not plan:
            return None
        validated = _validate(plan, ticker, peer_basket)
        return validated or None
    except Exception as e:
        print(f"[planner] LLM planning failed ({e}); using rule-based plan.")
        return None
