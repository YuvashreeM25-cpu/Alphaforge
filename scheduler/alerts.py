"""
Alert engine (Phase 4 automation).

Evaluates threshold rules against freshly computed analytics and delivers any
breaches. Delivery is via SMTP if configured (env below), otherwise printed and
stored in the `alerts` table so nothing is lost.

Env for email (all optional):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_FROM, ALERT_TO

Rules (defaults, override via env):
  ALERT_VAR_PCT   -> fire if a name's 1-day 95% VaR exceeds this (default 4.0)
  ALERT_DOWNSIDE  -> fire if DCF implies downside worse than this % (default -20)
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from data_pipeline.db import connect
from finance.valuation import dcf
from risk.montecarlo_var import monte_carlo_var

VAR_LIMIT = float(os.environ.get("ALERT_VAR_PCT", "4.0"))
DOWNSIDE_LIMIT = float(os.environ.get("ALERT_DOWNSIDE", "-20"))


def evaluate(watchlist) -> list[dict]:
    """Return a list of fired alerts for the watchlist."""
    fired = []
    for t in watchlist:
        try:
            d = dcf(t)
            if d.upside_pct <= DOWNSIDE_LIMIT:
                fired.append({"ticker": t, "rule": "dcf_downside",
                              "value": d.upside_pct,
                              "message": f"{t} DCF implies {d.upside_pct:+.1f}% "
                                         f"(fair ${d.fair_value_per_share} vs ${d.current_price})"})
            r = monte_carlo_var([t], n_paths=50_000)
            if r["VaR_pct"] >= VAR_LIMIT:
                fired.append({"ticker": t, "rule": "var_breach",
                              "value": r["VaR_pct"],
                              "message": f"{t} 1-day 95% VaR {r['VaR_pct']}% "
                                         f"exceeds limit {VAR_LIMIT}%"})
        except Exception as e:
            fired.append({"ticker": t, "rule": "error", "value": 0,
                          "message": f"{t}: could not evaluate ({e})"})
    _persist(fired)
    return fired


def _persist(fired):
    if not fired:
        return
    with connect() as conn:
        for a in fired:
            conn.execute(
                "INSERT INTO alerts(ticker, rule, value, message) VALUES (?,?,?,?)",
                (a["ticker"], a["rule"], a["value"], a["message"]),
            )


def deliver(subject: str, body: str) -> str:
    host = os.environ.get("SMTP_HOST")
    to = os.environ.get("ALERT_TO")
    if not host or not to:
        print(f"\n--- ALERT (no SMTP configured, printing) ---\n{subject}\n{body}\n")
        return "console"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("ALERT_FROM", os.environ.get("SMTP_USER", "alphaforge@example.com"))
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
        return "email"
    except Exception as e:
        print(f"[alerts] email failed ({e}); printing instead:\n{subject}\n{body}")
        return "console (email failed)"


if __name__ == "__main__":
    from data_pipeline.sample_data import generate
    generate()
    alerts = evaluate(["NVDA", "AMD", "INTC", "TSM"])
    print(f"{len(alerts)} alert(s) fired.")
    for a in alerts:
        print("  -", a["message"])
