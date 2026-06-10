# Olist Gold Mart — Executive Dashboard (Streamlit)

A narrated management deck over the `olist_gold_mart_prod` BigQuery gold mart
(1 `fact_orders` + 5 dims), built with **Streamlit + seaborn / matplotlib / plotly**.

It tells one connected story across five sections:

| Section | Audience | Question it answers |
|---|---|---|
| **Executive overview** | CEO | Is GMV growth bought or earned? (KPIs, new-vs-repeat GMV, CAC scenario) |
| **Retention & customers** | CMO | Why don't customers come back? (repeat trend, one-and-done, cohort heatmap, RFM) |
| **Delivery & experience** | CTO | Where does the experience break? (lead-time, late-rate map, review↔delivery) |
| **Product catalog** | — | Where is revenue concentrated? (top categories, category×state heatmap) |
| **The diagnosis** | All | The late-delivery → bad-review → no-reorder chain, with per-leader actions |

## Quickstart
```bash
make venv      # create .venv + install
make run       # → http://localhost:8501  (offline, from baked data/*.parquet)
```
See [`notes/setup.local.md`](notes/setup.local.md) for live-BigQuery mode and snapshot refresh,
and [`notes/setup.prod.md`](notes/setup.prod.md) for the Cloud Run deploy.

## Design
- **Offline by default** (`DASH_OFFLINE=1`): the app reads `data/*.parquet`, never BigQuery —
  fast, free, and reliable for a live presentation. Set `DASH_OFFLINE=0` for live queries.
- **Two SQL pulls, all derivation in pandas** (`queries.py` → `metrics.py`) so distinct-count
  metrics (repeat rate, retention) stay correct under any date/state filter.
- Shares the data + metrics layer with the Plotly Dash version in [`../dash/`](../dash); only
  the presentation layer (`charts.py`, `app.py`) differs.

> Marketing spend / CAC / margin are **illustrative finance assumptions**, not warehouse data
> — the overview scenario tool makes that explicit.
