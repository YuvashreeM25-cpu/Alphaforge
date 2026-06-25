# AlphaForge — Product Brief

*The Section-2 "market research" deliverable. Written before code, in plain language,
to show a user-first build.*

## 1. The user: the buy-side equity analyst
A junior-to-mid analyst at a hedge fund or asset manager covering a sector
(say semiconductors). A normal day is **fragmented**: a Bloomberg Terminal for
prices and news, Excel for the DCF model, broker PDFs and 10-Ks for fundamentals,
a transcript service for earnings calls, and a Slack channel arguing about all of
it. Producing a *first-draft* investment thesis on a new name — pull the numbers,
build a quick valuation, sanity-check risk, write it up — realistically eats
**2–3 hours**, most of it plumbing rather than thinking.

The pain is not "no data." The pain is **assembly**: the numbers live in five
tools that don't talk to each other, and the analyst is the integration layer.

## 2. Market / competitor teardown
- **Bloomberg Terminal** — the incumbent. Unmatched data breadth, real-time feeds,
  chat. ~$30k/user/year. It is a *data and messaging* terminal, not an opinionated
  research-automation layer; it hands you everything and assembles nothing.
- **AlphaSense** — AI search over filings, transcripts, and broker research.
  Strong for *finding* a fact fast; priced for enterprises. It surfaces documents,
  it does not build your valuation or simulate your portfolio risk.
- **Koyfin** — excellent, affordable ($0–~$100/mo) charting and fundamentals; a
  retail/prosumer Bloomberg-lite. Great dashboards, but no agentic workflow and no
  custom modelling.
- **Tegus** — expert-call transcripts and primary research. Deep qualitative
  colour; orthogonal to quantitative valuation/risk.
- **FactSet** — Bloomberg's main rival; rich data + Excel integration, enterprise
  pricing. Again a *data + tooling* platform, not a workflow that plans and writes
  a thesis.

The common gap: these are **data and retrieval** tools. None of them *executes an
analyst's reasoning workflow end to end* — pull fundamentals, screen peers, run a
DCF, simulate downside, and hand back a cited draft thesis.

## 3. The wedge
**AlphaForge turns a plain-English question into a planned, multi-step research
workflow whose every number is computed by transparent, auditable code — and whose
prose is written by an LLM that is structurally forbidden from inventing a number.**

## 4. Success metric
Reduce time-to-first-draft thesis from **~3 hours to ~10 minutes**, with full
traceability of every figure back to the tool that produced it. Secondary metric:
zero un-sourced numbers in the output (enforced by design, not by review).

## 5. Explicitly out of scope (v1)
Real-time tick data, execution/OMS integration, options analytics, and compliance
archiving. AlphaForge is a *research drafting* workbench, not a trading system.
