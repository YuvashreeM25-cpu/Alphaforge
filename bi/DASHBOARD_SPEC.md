# AlphaForge BI Dashboard — Build Spec

A separate BI artifact built on AlphaForge's own analytics. Generate the data
source first:

```bash
python -m bi.export      # writes bi/output/alphaforge_bi.xlsx + CSVs
```

Then connect **Tableau** (or **Power BI**) to `bi/output/alphaforge_bi.xlsx`
(or the individual CSVs). Sheets: `Holdings`, `SectorExposure`, `Risk`, `Summary`.

## Data model
Single fact table `Holdings` (one row per ticker) plus two aggregates
(`SectorExposure`, `Risk`). In Power BI, relate `Risk[ticker]` and
`Holdings[ticker]` (many-to-one is unnecessary — keep them as separate tables and
join on `ticker` only if you want cross-filtering).

| Field | Table | Meaning |
|---|---|---|
| `ticker`, `sector` | Holdings | identity / grouping |
| `price`, `market_cap_mm` | Holdings | size |
| `pe`, `ev_ebitda`, `roic_pct`, `ebitda_margin_pct`, `net_debt_ebitda` | Holdings | factors |
| `dcf_fair_value`, `dcf_upside_pct` | Holdings | valuation output |
| `ml_p_outperform` | Holdings | model confidence (0–1) |
| `var_95_pct`, `cvar_95_pct` | Risk | per-name + portfolio risk |

## Views to build (4 tiles + filters)

### 1. Portfolio Overview (KPI strip)
- Cards: # names (`COUNT`), total market cap (`SUM(market_cap_mm)`),
  avg DCF upside (`AVG(dcf_upside_pct)`), median EV/EBITDA.
- These mirror the `Summary` sheet so you can sanity-check the BI layer.

### 2. Sector Exposure (bar / treemap)
- Source: `SectorExposure`. Treemap sized by `market_cap_mm`, colored by
  `avg_roic_pct`. Answers "where is the book concentrated, and is that
  concentration high- or low-quality?"

### 3. Risk Heatmap (highlight table)
- Source: `Risk`. Rows = `ticker`, color = `var_95_pct` (sequential red).
- Include the `PORTFOLIO(EW)` row as a reference line; diversification should
  put it below the average single-name VaR.

### 4. Valuation vs Quality (scatter)
- Source: `Holdings`. X = `ev_ebitda`, Y = `roic_pct`, size = `market_cap_mm`,
  color = `dcf_upside_pct` (diverging). Label = `ticker`.
- The top-left quadrant (cheap + high quality) is the classic value-quality
  screen; names there with positive DCF upside are the ideas.

### 5. Model Confidence (optional bar)
- Source: `Holdings`. Bar of `ml_p_outperform` by `ticker`, reference line at
  0.5. Communicates that the model is a *weak tilt*, not a forecast.

## Filters / interactivity
- Global `sector` filter applied to all tiles.
- A `dcf_upside_pct` range slider to isolate undervalued names.

## Refresh
Re-run `python -m bi.export` after each data refresh (the nightly scheduler can
call it), then hit Refresh in Tableau/Power BI. For a live demo, Tableau Public
or Power BI Service can host a published version as the standalone BI artifact.
