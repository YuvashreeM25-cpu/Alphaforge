"""
AlphaForge end-to-end demo — the "just run this" entry point.

    python run_demo.py
    python run_demo.py --question "Is AMD cheap vs its peers?"
    python run_demo.py --live          # pull real prices from yfinance first

Runs the whole pipeline: data -> features+ML -> valuation -> risk -> agent.
No API keys required. Set ANTHROPIC_API_KEY for nicer LLM-written prose.
"""
from __future__ import annotations

import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", default="Is NVDA overvalued vs its semiconductor peers given the downside risk?")
    ap.add_argument("--live", action="store_true", help="Pull real prices via yfinance first")
    ap.add_argument("--retrain", action="store_true", help="Force model retrain")
    ap.add_argument("--llm-planner", action="store_true",
                    help="Use the LLM planner (needs ANTHROPIC_API_KEY; falls back to rules)")
    args = ap.parse_args()

    print("=" * 70)
    print("ALPHAFORGE — end-to-end demo")
    print("=" * 70)

    print("\n[1/4] Building dataset...")
    if args.live:
        from data_pipeline.ingest import ingest_live
        ingest_live()
    else:
        from data_pipeline.sample_data import generate
        generate()

    print("\n[2/4] Training the ML model (time-aware split)...")
    from models.train_classifier import train, MODEL_PATH
    if args.retrain or not MODEL_PATH.exists():
        m = train()
    else:
        import json
        from models.train_classifier import METRICS_PATH
        m = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else train()
    test = m.get("test", {})
    print(f"      test AUC={test.get('auc')}  accuracy={test.get('accuracy')}  "
          f"(train AUC={m.get('train', {}).get('auc')})")
    print("      ^ train >> test is the leakage check working: synthetic data has no real alpha.")

    print("\n[3/4] Running the agent...")
    from agent.orchestrator import run
    r = run(args.question, use_llm_planner=args.llm_planner)
    print(f"      ticker: {r.ticker}")
    print(f"      plan:   {' -> '.join(s['tool'] for s in r.steps)}")
    for s in r.steps:
        print(f"        - {s['tool']:12} {s['summary']}")

    print("\n[4/4] Thesis:\n")
    print(r.thesis)
    print("\n" + "=" * 70)
    print("Done. Try:  python run_demo.py --question \"Is AMD cheap vs peers?\"")
    print("Interactive UI:  uvicorn api.main:app --reload   then open frontend/index.html")
    print("=" * 70)


if __name__ == "__main__":
    main()
