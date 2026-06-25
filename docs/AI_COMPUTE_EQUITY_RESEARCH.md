# The AI-Compute Supply Chain — An Equity-Research Primer

*Section-9 deliverable: the honest way to show "AI chips" literacy as a finance
person rather than pretending to be a hardware engineer. Covers the economics,
where the margin pools, the real bottlenecks, and a valuation lens. The tickers
below are the same ones AlphaForge loads in Phase 1.*

> Note: this is an educational research note, not investment advice, and the
> figures are illustrative round numbers for teaching the structure of the chain.

## 1. The capex story
The AI build-out is a capital-expenditure supercycle: hyperscalers
(Microsoft, Alphabet, Amazon, Meta) are spending heavily on data-center compute.
For an equity analyst the key questions are (a) how durable is the spend, (b) who
converts it into *margin*, and (c) where the capacity bottlenecks gate growth.

## 2. Where the margin pools (the value chain, top to bottom)
- **GPU / accelerator design — NVIDIA (NVDA), AMD (AMD).** This is where the
  fattest margins sit today. NVIDIA's moat is as much **software (CUDA) and
  systems (NVLink, networking)** as silicon; that ecosystem lock-in is the core
  of the bull case and the main thing a bear must argue erodes.
- **Custom silicon / networking — Broadcom (AVGO).** Designs custom accelerators
  (ASICs) for hyperscalers and owns critical networking. A pick-and-shovel way to
  play AI capex that is less exposed to the merchant-GPU share war.
- **Foundry — TSMC (TSM).** Manufactures the leading-edge chips for nearly
  everyone. Effectively a tollbooth on advanced compute; the question is pricing
  power vs. its own enormous capex and customer concentration.
- **Lithography — ASML (ASML).** Sole supplier of EUV lithography machines.
  The narrowest bottleneck in the entire chain — without ASML, no leading-edge
  foundry capacity exists. Monopoly economics, but capital-cycle and
  export-control exposed.
- **Memory — Micron (MU), SK Hynix, Samsung.** **High-Bandwidth Memory (HBM)** is
  the single tightest near-term bottleneck: every top-tier accelerator needs
  stacks of it, and supply is sold out well ahead. Memory is historically
  cyclical/commoditized, so the debate is whether HBM is *structurally* different.
- **Incumbent under pressure — Intel (INTC).** The cautionary tale: lost the
  process lead, heavy debt, negative recent earnings — a useful short/relative
  case study against the leaders.

## 3. The three bottlenecks that actually gate growth
1. **EUV lithography (ASML).** Upstream choke point; machine output caps everything.
2. **Advanced packaging (e.g. TSMC CoWoS).** Stitching logic + HBM together has
   been a real throughput limiter even when wafers exist.
3. **HBM memory.** Demand outruns supply; allocation, not desire, sets near-term unit growth.

The investing insight: **margin accrues to whoever owns the tightest bottleneck.**
That is why a foundry, a lithography monopoly, and a memory maker can be more
interesting risk/reward than the headline GPU names at the wrong price.

## 4. A valuation lens (how AlphaForge would frame it)
For each name, triangulate:
- **DCF** — is the AI-capex growth already in the cash flows? Run the sensitivity
  grid (WACC × terminal growth) AlphaForge produces; these names live or die on
  terminal assumptions.
- **Comparables (EV/EBITDA vs sector median)** — who screens cheap *relative to
  their position in the chain*? A monopoly (ASML) deserves a premium; a
  commoditized cyclical (memory) does not — until the cycle turns.
- **Quality (ROIC, margins)** — the bottleneck owners post structurally higher
  returns on capital. That is the quantitative fingerprint of the moat.

## 5. The one-paragraph view
The durable way to express the AI theme may be **less about the GPU and more about
the bottleneck**: lithography (ASML), leading-edge foundry (TSM), and HBM (MU and
peers). The GPU designers (NVDA, AMD) carry the highest growth *and* the highest
expectations, so the risk/reward turns heavily on price and on whether the CUDA
software moat holds. The analyst's job is to separate *the theme is real* (it is)
from *this multiple already prices it in* (sometimes) — which is exactly the
valuation-vs-quality-vs-risk triangulation AlphaForge automates.
