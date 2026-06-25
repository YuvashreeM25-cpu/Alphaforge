"""
Live ingestion pipeline (Phase 1, upgraded).

Sources, in order of preference, with graceful fallback at every step:
  * prices       -> yfinance (Yahoo Finance)
  * fundamentals -> yfinance .info, then SEC EDGAR companyfacts as a cross-check

Run:
  python -m data_pipeline.ingest                 # synthetic (offline, default)
  python -m data_pipeline.ingest --live          # real prices + fundamentals
  python -m data_pipeline.ingest --live --edgar  # also pull SEC EDGAR fundamentals

Every run is recorded in the ingest_log table (success/failure counts) so the
nightly scheduler can report on data health.
"""
from __future__ import annotations

import argparse
import json
import sys

from .db import connect, init_db
from .sample_data import UNIVERSE, generate


def _log_run(source, ok, failed, detail):
    with connect() as conn:
        conn.execute(
            "INSERT INTO ingest_log(source, ok, failed, detail) VALUES (?,?,?,?)",
            (source, ok, failed, json.dumps(detail)[:2000]),
        )


def _validate_prices(rows):
    clean = []
    for t, d, c, v in rows:
        if c is None or c <= 0 or not d:
            continue
        clean.append((t, d, round(float(c), 2), float(v or 0)))
    return clean


def _yf_fundamentals(tk) -> dict | None:
    """Map a yfinance .info dict to our schema ($millions)."""
    try:
        info = tk.info or {}
    except Exception:
        return None

    def mm(x):
        return round(x / 1e6, 1) if isinstance(x, (int, float)) else None

    rev = mm(info.get("totalRevenue"))
    ebitda = mm(info.get("ebitda"))
    ni = mm(info.get("netIncomeToCommon"))
    fcf = mm(info.get("freeCashflow"))
    debt = mm(info.get("totalDebt"))
    cash = mm(info.get("totalCash"))
    shares = info.get("sharesOutstanding")
    if rev is None and ni is None:
        return None
    return {
        "revenue": rev, "ebitda": ebitda, "net_income": ni, "fcf": fcf,
        "total_debt": debt, "cash": cash, "equity": None,
        "shares_out": round(shares / 1e6, 1) if shares else None,
        "source": "yfinance",
    }


def ingest_live(tickers=None, use_edgar=False) -> None:
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed (pip install yfinance). Using synthetic data.",
              file=sys.stderr)
        generate()
        return

    init_db()
    meta = {u[0]: u for u in UNIVERSE}
    tickers = tickers or [u[0] for u in UNIVERSE]
    ok, failed = 0, []

    for t in tickers:
        try:
            tk = yf.Ticker(t)
            hist = tk.history(period="2y", interval="1d", auto_adjust=True)
            if hist is None or hist.empty:
                raise ValueError("empty price history")

            m = meta.get(t)
            name = m[1] if m else t
            sector = m[2] if m else (tk.info.get("sector") or "Unknown")
            shares = m[3] if m else 1000

            fund = _yf_fundamentals(tk)
            if fund and fund.get("shares_out"):
                shares = fund["shares_out"]

            with connect() as conn:
                conn.upsert("companies",
                            {"ticker": t, "name": name, "sector": sector, "shares_out": shares},
                            ["ticker"])
                rows = [(t, idx.date().isoformat(), float(r["Close"]), float(r.get("Volume", 0)))
                        for idx, r in hist.iterrows()]
                for row in _validate_prices(rows):
                    conn.upsert("prices",
                                {"ticker": row[0], "date": row[1], "close": row[2], "volume": row[3]},
                                ["ticker", "date"])

                # fundamentals: EDGAR if requested and available, else yfinance
                fdict = None
                if use_edgar:
                    from .edgar import fetch_edgar_fundamentals
                    fdict = fetch_edgar_fundamentals(t)
                if fdict is None:
                    fdict = fund
                if fdict:
                    fdict = {k: v for k, v in fdict.items() if k != "shares_out"}
                    fdict.update({"ticker": t, "period": "TTM"})
                    conn.upsert("fundamentals", fdict, ["ticker", "period"])

            ok += 1
            print(f"  [ok] {t}: {len(rows)} price rows"
                  + (f", fundamentals via {fdict.get('source')}" if fdict else ""))
        except Exception as e:
            failed.append((t, str(e)))
            print(f"  [skip] {t}: {e}", file=sys.stderr)

    _log_run("live", ok, len(failed), {"failed": failed})
    print(f"Ingestion complete. {ok} ok, {len(failed)} failed (logged to ingest_log).")


def main():
    ap = argparse.ArgumentParser(description="AlphaForge data ingestion")
    ap.add_argument("--live", action="store_true", help="Pull real data from yfinance")
    ap.add_argument("--edgar", action="store_true", help="Also pull SEC EDGAR fundamentals")
    args = ap.parse_args()
    if args.live:
        ingest_live(use_edgar=args.edgar)
    else:
        generate()
        _log_run("synthetic", len(UNIVERSE), 0, {})


if __name__ == "__main__":
    main()
