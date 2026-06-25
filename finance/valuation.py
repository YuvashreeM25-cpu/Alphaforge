"""
Valuation engine (Phase 3 — the finance core).

Two independent methods, written explicitly so a reviewer can read the math:
  1) Discounted Cash Flow (DCF) with a Gordon terminal value.
  2) Comparables (EV/EBITDA multiple vs sector peers).

Plus a sensitivity table over WACC x terminal growth — the thing every
buy-side analyst actually stares at.

Every number returned here is computed from stored fundamentals. Nothing is
guessed. The agent's LLM layer is only allowed to *describe* these outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from data_pipeline.db import connect


@dataclass
class DCFResult:
    ticker: str
    enterprise_value: float          # millions
    equity_value: float              # millions
    fair_value_per_share: float
    current_price: float
    upside_pct: float
    assumptions: dict = field(default_factory=dict)
    sensitivity: list = field(default_factory=list)  # rows of dicts


def _latest_price(ticker: str) -> float:
    with connect() as conn:
        row = conn.execute(
            "SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1", (ticker,)
        ).fetchone()
    if not row:
        raise ValueError(f"No price for {ticker}")
    return float(row["close"])


def _fundamentals(ticker: str) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM fundamentals WHERE ticker=? ORDER BY period DESC LIMIT 1", (ticker,)
        ).fetchone()
        co = conn.execute("SELECT * FROM companies WHERE ticker=?", (ticker,)).fetchone()
    if not row or not co:
        raise ValueError(f"No fundamentals for {ticker}")
    d = dict(row)
    d["shares_out"] = float(co["shares_out"])
    d["sector"] = co["sector"]
    return d


def dcf(ticker: str, wacc: float = 0.10, term_growth: float = 0.03,
        fcf_growth: float = 0.08, years: int = 5) -> DCFResult:
    """
    Project FCF for `years`, discount at `wacc`, add a Gordon terminal value,
    subtract net debt to get equity value, divide by shares.
    """
    f = _fundamentals(ticker)
    fcf0 = f["fcf"]
    net_debt = (f["total_debt"] or 0) - (f["cash"] or 0)
    shares = f["shares_out"]

    # discounted explicit-period cash flows
    pv_sum = 0.0
    fcf_t = fcf0
    for t in range(1, years + 1):
        fcf_t = fcf_t * (1 + fcf_growth)
        pv_sum += fcf_t / (1 + wacc) ** t

    # terminal value (Gordon growth) discounted back
    fcf_terminal = fcf_t * (1 + term_growth)
    terminal_value = fcf_terminal / (wacc - term_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years

    enterprise_value = pv_sum + pv_terminal
    equity_value = enterprise_value - net_debt
    fair_value = equity_value / shares
    price = _latest_price(ticker)

    return DCFResult(
        ticker=ticker,
        enterprise_value=round(enterprise_value, 1),
        equity_value=round(equity_value, 1),
        fair_value_per_share=round(fair_value, 2),
        current_price=round(price, 2),
        upside_pct=round((fair_value / price - 1) * 100, 1),
        assumptions=dict(wacc=wacc, term_growth=term_growth,
                         fcf_growth=fcf_growth, years=years,
                         fcf0=fcf0, net_debt=net_debt, shares_out=shares),
        sensitivity=_sensitivity(fcf0, net_debt, shares, price, fcf_growth, years),
    )


def _sensitivity(fcf0, net_debt, shares, price, fcf_growth, years) -> list:
    """Fair-value-per-share grid over WACC (rows) x terminal growth (cols)."""
    waccs = [0.08, 0.09, 0.10, 0.11, 0.12]
    growths = [0.02, 0.025, 0.03, 0.035, 0.04]
    table = []
    for w in waccs:
        row = {"wacc": w}
        for g in growths:
            fcf_t = fcf0
            pv = 0.0
            for t in range(1, years + 1):
                fcf_t *= (1 + fcf_growth)
                pv += fcf_t / (1 + w) ** t
            tv = (fcf_t * (1 + g)) / (w - g)
            pv += tv / (1 + w) ** years
            fv = (pv - net_debt) / shares
            row[f"g={g:.3f}"] = round(fv, 2)
        table.append(row)
    return table


def comparables(ticker: str) -> dict:
    """EV/EBITDA-based fair value using the sector peer median multiple."""
    f = _fundamentals(ticker)
    sector = f["sector"]
    with connect() as conn:
        peers = conn.execute(
            "SELECT ticker FROM companies WHERE sector=? AND ticker!=?", (sector, ticker)
        ).fetchall()
    multiples = []
    for p in peers:
        pf = _fundamentals(p["ticker"])
        if not pf["ebitda"] or pf["ebitda"] <= 0:
            continue
        price = _latest_price(p["ticker"])
        mkt_cap = price * pf["shares_out"]
        ev = mkt_cap + (pf["total_debt"] or 0) - (pf["cash"] or 0)
        multiples.append(ev / pf["ebitda"])
    if not multiples:
        return {"ticker": ticker, "error": "no comparable peers with positive EBITDA"}

    peer_multiple = median(multiples)
    implied_ev = peer_multiple * f["ebitda"] if f["ebitda"] > 0 else None
    price = _latest_price(ticker)
    own_mktcap = price * f["shares_out"]
    own_ev = own_mktcap + (f["total_debt"] or 0) - (f["cash"] or 0)
    own_multiple = own_ev / f["ebitda"] if f["ebitda"] > 0 else None

    out = {
        "ticker": ticker,
        "sector": sector,
        "peer_median_ev_ebitda": round(peer_multiple, 1),
        "own_ev_ebitda": round(own_multiple, 1) if own_multiple else None,
        "current_price": round(price, 2),
    }
    if implied_ev and f["ebitda"] > 0:
        implied_equity = implied_ev - ((f["total_debt"] or 0) - (f["cash"] or 0))
        implied_price = implied_equity / f["shares_out"]
        out["implied_fair_value"] = round(implied_price, 2)
        out["upside_pct"] = round((implied_price / price - 1) * 100, 1)
    return out


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    r = dcf("NVDA")
    print(f"NVDA DCF fair value: ${r.fair_value_per_share} vs ${r.current_price} "
          f"({r.upside_pct:+.1f}%)")
    print("Comparables:", comparables("NVDA"))
