"""
Fundamental factor analysis + universe ranking (Phase 3).

Computes standard buy-side factors per ticker and ranks the universe.
Also powers the simple "screener" tool the agent calls.
"""
from __future__ import annotations

from data_pipeline.db import connect


def _latest_price(conn, ticker):
    row = conn.execute(
        "SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1", (ticker,)
    ).fetchone()
    return float(row["close"]) if row else None


def factor_table() -> list[dict]:
    """One row per company with valuation/quality/leverage factors."""
    rows = []
    with connect() as conn:
        companies = conn.execute("SELECT * FROM companies").fetchall()
        for co in companies:
            t = co["ticker"]
            f = conn.execute(
                "SELECT * FROM fundamentals WHERE ticker=? ORDER BY period DESC LIMIT 1", (t,)
            ).fetchone()
            if not f:
                continue
            price = _latest_price(conn, t)
            if price is None:
                continue
            mktcap = price * co["shares_out"]
            ev = mktcap + (f["total_debt"] or 0) - (f["cash"] or 0)
            pe = mktcap / f["net_income"] if f["net_income"] and f["net_income"] > 0 else None
            ev_ebitda = ev / f["ebitda"] if f["ebitda"] and f["ebitda"] > 0 else None
            invested_capital = (f["total_debt"] or 0) + (f["equity"] or 0) - (f["cash"] or 0)
            roic = (f["net_income"] / invested_capital * 100) if invested_capital else None
            ebitda_margin = (f["ebitda"] / f["revenue"] * 100) if f["revenue"] else None
            leverage = ((f["total_debt"] or 0) / f["ebitda"]) if f["ebitda"] and f["ebitda"] > 0 else None
            rows.append({
                "ticker": t, "sector": co["sector"],
                "price": round(price, 2),
                "market_cap": round(mktcap, 0),
                "pe": round(pe, 1) if pe else None,
                "ev_ebitda": round(ev_ebitda, 1) if ev_ebitda else None,
                "roic_pct": round(roic, 1) if roic else None,
                "ebitda_margin_pct": round(ebitda_margin, 1) if ebitda_margin else None,
                "net_debt_ebitda": round(leverage, 2) if leverage is not None else None,
            })
    return rows


def screen(max_ev_ebitda: float | None = None, min_roic: float | None = None,
           sector: str | None = None) -> list[dict]:
    """Filter the universe by simple rules — the agent's screener tool."""
    out = []
    for r in factor_table():
        if sector and r["sector"] != sector:
            continue
        if max_ev_ebitda is not None and (r["ev_ebitda"] is None or r["ev_ebitda"] > max_ev_ebitda):
            continue
        if min_roic is not None and (r["roic_pct"] is None or r["roic_pct"] < min_roic):
            continue
        out.append(r)
    return out


def rank_by(metric: str = "roic_pct", descending: bool = True) -> list[dict]:
    rows = [r for r in factor_table() if r.get(metric) is not None]
    return sorted(rows, key=lambda r: r[metric], reverse=descending)


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    for r in rank_by("roic_pct")[:5]:
        print(f"{r['ticker']:5} ROIC {r['roic_pct']}%  EV/EBITDA {r['ev_ebitda']}")
