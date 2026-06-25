"""
SEC EDGAR fundamentals (free, no API key — just a descriptive User-Agent).

Pulls the latest annual values from the XBRL companyfacts API:
  https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

The SEC asks that automated clients send a User-Agent identifying them; set
SEC_USER_AGENT="Your Name your@email.com". Returns a dict matching our schema, or
None if anything is missing so the caller can fall back to another source.
"""
from __future__ import annotations

import json
import os
import urllib.request

SEC_UA = os.environ.get("SEC_USER_AGENT", "AlphaForge research alphaforge@example.com")
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

_cik_cache: dict[str, int] = {}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _cik_for(ticker: str) -> int | None:
    if not _cik_cache:
        try:
            data = _get_json(_TICKER_MAP_URL)
            for row in data.values():
                _cik_cache[row["ticker"].upper()] = int(row["cik_str"])
        except Exception:
            return None
    return _cik_cache.get(ticker.upper())


def _latest_annual(facts: dict, tag: str):
    """Most recent annual (FY) USD value for a us-gaap concept."""
    try:
        units = facts["facts"]["us-gaap"][tag]["units"]["USD"]
    except KeyError:
        return None
    annual = [u for u in units if u.get("form") in ("10-K", "20-F") and u.get("fp") == "FY"]
    if not annual:
        annual = units
    annual.sort(key=lambda u: u.get("end", ""))
    return annual[-1]["val"] if annual else None


def fetch_edgar_fundamentals(ticker: str) -> dict | None:
    cik = _cik_for(ticker)
    if cik is None:
        return None
    try:
        facts = _get_json(_FACTS_URL.format(cik=cik))
    except Exception:
        return None

    def mm(tag):
        v = _latest_annual(facts, tag)
        return round(v / 1e6, 1) if v is not None else None  # to $millions

    revenue = mm("RevenueFromContractWithCustomerExcludingAssessedTax") or mm("Revenues")
    net_income = mm("NetIncomeLoss")
    op_income = mm("OperatingIncomeLoss")
    dep = mm("DepreciationDepletionAndAmortization") or 0
    ebitda = (op_income + dep) if op_income is not None else None
    cfo = mm("NetCashProvidedByUsedInOperatingActivities")
    capex = mm("PaymentsToAcquirePropertyPlantAndEquipment") or 0
    fcf = (cfo - capex) if cfo is not None else None
    debt = mm("LongTermDebtNoncurrent") or mm("LongTermDebt")
    cash = mm("CashAndCashEquivalentsAtCarryingValue")
    equity = mm("StockholdersEquity")

    if revenue is None and net_income is None:
        return None
    return {
        "revenue": revenue, "ebitda": ebitda, "net_income": net_income,
        "fcf": fcf, "total_debt": debt, "cash": cash, "equity": equity,
        "source": "sec_edgar",
    }


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    print(t, fetch_edgar_fundamentals(t))
