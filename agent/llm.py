"""
LLM layer (Phase 4) — used ONLY for two things:
  1) turn a plain-English question into a PLAN (ordered tool calls)
  2) turn the computed numbers into readable prose

It must never invent a number. If ANTHROPIC_API_KEY is set, we use the API for
nicer prose; otherwise a deterministic template composer runs so the whole repo
works offline with zero keys. Either way the numbers come from our tools.
"""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("ALPHAFORGE_LLM_MODEL", "claude-sonnet-4-6")


def _have_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_anthropic(system: str, user: str) -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    except Exception as e:  # never let the LLM break the run
        print(f"[llm] API call failed ({e}); using template composer.")
        return None


def compose_thesis(question: str, ticker: str, evidence: dict) -> str:
    """
    Compose the final thesis. Numbers are pre-computed in `evidence`; the LLM (or
    template) only narrates them. We pass evidence as JSON and instruct the model
    to use ONLY those numbers.
    """
    if _have_key():
        system = (
            "You are a buy-side equity analyst. Write a concise, structured "
            "investment thesis. CRITICAL RULE: use ONLY the numbers provided in "
            "the evidence JSON. Never invent or estimate any figure. Cite which "
            "tool each number came from in parentheses, e.g. (valuation), (risk)."
        )
        user = (f"Question: {question}\nTicker: {ticker}\n"
                f"Evidence (the ONLY numbers you may use):\n{json.dumps(evidence, indent=2)}")
        out = _call_anthropic(system, user)
        if out:
            return out
    return _template_thesis(question, ticker, evidence)


def _template_thesis(question: str, ticker: str, e: dict) -> str:
    """Deterministic fallback — still cites tool sources, still no invented numbers."""
    val = e.get("valuation", {})
    risk = e.get("risk", {})
    ml = e.get("ml_score", {})
    fund = e.get("fundamentals", {})
    lines = [f"# Investment Thesis — {ticker}", "", f"_Question: {question}_", ""]

    if val:
        dcf_fv = val.get("dcf_fair_value")
        up = val.get("dcf_upside_pct")
        px = val.get("current_price")
        comps = val.get("comparables", {})
        lines += [
            "## Valuation (source: valuation tool)",
            f"- DCF fair value **${dcf_fv}** vs current **${px}** "
            f"({up:+.1f}% implied {'upside' if up and up > 0 else 'downside'}).",
        ]
        if comps.get("implied_fair_value"):
            lines.append(
                f"- Comparables (sector median EV/EBITDA {comps.get('peer_median_ev_ebitda')}x) "
                f"imply **${comps['implied_fair_value']}** ({comps.get('upside_pct'):+.1f}%); "
                f"the name trades at {comps.get('own_ev_ebitda')}x itself.")
        lines.append("")

    if fund and "error" not in fund:
        lines += [
            "## Quality & leverage (source: fundamentals tool)",
            f"- ROIC {fund.get('roic_pct')}%, EBITDA margin {fund.get('ebitda_margin_pct')}%, "
            f"net debt/EBITDA {fund.get('net_debt_ebitda')}x.",
            "",
        ]

    if ml and "error" not in ml:
        lines += [
            "## Model signal (source: ml_score tool)",
            f"- Modeled probability of outperforming the sector next month: "
            f"**{ml.get('p_outperform_sector_1m')}** (as of {ml.get('as_of')}). "
            f"Treat as a weak tilt, not a forecast.",
            "",
        ]

    if risk:
        lines += [
            "## Risk (source: risk tool — Monte-Carlo VaR)",
            f"- 1-day 95% VaR **{risk.get('VaR_pct')}%**, CVaR {risk.get('CVaR_pct')}% "
            f"on an equal-weight basket of {', '.join(risk.get('tickers', []))} "
            f"({risk.get('n_paths'):,} simulated paths).",
            "",
        ]

    lines += [
        "## Bottom line",
        _verdict(val),
        "",
        "_All figures computed by AlphaForge tools; prose generated without "
        "inventing any number._",
    ]
    return "\n".join(lines)


def _verdict(val: dict) -> str:
    up = val.get("dcf_upside_pct") if val else None
    if up is None:
        return "- Insufficient valuation data for a directional call."
    if up > 25:
        return f"- DCF suggests meaningful undervaluation ({up:+.1f}%); constructive, pending risk sizing."
    if up < -15:
        return f"- DCF suggests overvaluation ({up:+.1f}%); cautious."
    return f"- DCF implies roughly fair value ({up:+.1f}%); no strong edge from price alone."
