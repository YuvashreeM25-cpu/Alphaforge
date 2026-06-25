"""
Nightly automation (Phase 4).

The daily job:
  1. refresh data (live if --live, else regenerate synthetic)
  2. retrain the ML model on the new data
  3. run the agent across a watchlist -> a "daily research brief"
  4. evaluate threshold alerts and deliver them

Usage:
  python -m scheduler.jobs --once           # run the whole job right now
  python -m scheduler.jobs --once --live     # ... pulling real data first
  python -m scheduler.jobs --serve           # run every day at 06:30 (blocking)

The watchlist comes from WATCHLIST env (comma-separated) or defaults to the
AI-compute names.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

WATCHLIST = [t.strip().upper() for t in
             os.environ.get("WATCHLIST", "NVDA,AMD,TSM,ASML,MU,INTC").split(",") if t.strip()]


def run_daily(live: bool = False) -> str:
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] daily job starting "
          f"(watchlist: {', '.join(WATCHLIST)})")

    # 1. data
    if live:
        from data_pipeline.ingest import ingest_live
        ingest_live(use_edgar=os.environ.get("USE_EDGAR") == "1")
    else:
        from data_pipeline.sample_data import generate
        generate()

    # 2. retrain
    from models.train_classifier import train
    metrics = train()
    print(f"  model retrained — test AUC={metrics.get('test', {}).get('auc')}")

    # 3. brief
    from agent.orchestrator import run as run_agent
    brief_lines = [f"AlphaForge daily brief — {datetime.now():%Y-%m-%d}", ""]
    for t in WATCHLIST:
        try:
            r = run_agent(f"Quick read on {t} including downside risk")
            val = r.memory.get("valuation", {})
            risk = r.memory.get("risk", {})
            brief_lines.append(
                f"{t}: DCF {val.get('dcf_upside_pct')}% upside, "
                f"95% VaR {risk.get('VaR_pct')}%")
        except Exception as e:
            brief_lines.append(f"{t}: error ({e})")
    brief = "\n".join(brief_lines)

    # 4. alerts
    from scheduler.alerts import evaluate, deliver
    alerts = evaluate(WATCHLIST)
    if alerts:
        brief += "\n\nALERTS:\n" + "\n".join(f"  - {a['message']}" for a in alerts)

    channel = deliver(f"AlphaForge brief {datetime.now():%Y-%m-%d} "
                      f"({len(alerts)} alert(s))", brief)
    print(f"  brief delivered via: {channel}")
    print(brief)
    return brief


def serve():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    sched = BlockingScheduler()
    live = os.environ.get("SCHED_LIVE") == "1"
    sched.add_job(lambda: run_daily(live=live),
                  CronTrigger(hour=6, minute=30), id="daily_brief")
    print("Scheduler started — daily brief at 06:30. Ctrl+C to stop.")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Run the job immediately")
    ap.add_argument("--serve", action="store_true", help="Run on a daily schedule")
    ap.add_argument("--live", action="store_true", help="Pull real data first")
    args = ap.parse_args()
    if args.serve:
        serve()
    else:
        run_daily(live=args.live)


if __name__ == "__main__":
    main()
