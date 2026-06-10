# Olist — Executive Dashboard (Plotly Dash)

A presentation-grade dashboard over the **`olist_gold_mart_prod`** gold mart that settles
one management argument with data:

> GMV is growing but marketing spend keeps climbing to sustain it. **Why?** Because the
> **repeat-purchase rate is the binding constraint (~3%)**, and the upstream cause of weak
> retention is **delivery experience → review scores**. The CTO's "logistics noise" is the
> CMO's churn is the CEO's soft margin — one problem, three symptoms.

Built with Plotly (figures) + Dash + dash-mantine-components ("bold data-story" theme).

## Tabs
| Tab | Lens | The point it proves |
|---|---|---|
| **Executive overview** | CEO | Growth is bought: only a sliver of GMV is repeat; editable CAC scenario shows the cost. |
| **Retention & customers** | CMO | ~97% buy once; cohorts collapse after month 0 — it's first-purchase experience, not brand. |
| **Delivery & experience** | CTO | Review score falls **4.29★ → 1.69★** as delivery slips late; late-rate choropleth by state. |
| **The diagnosis** | Synthesis | Late delivery → low review → lower repeat → acquisition treadmill → soft margin, + per-exec actions. |

## Architecture
```
BigQuery gold mart ──> queries.py (2 result sets) ──> bq.py (parquet cache) ──>
metrics.py (pandas: repeat, cohort, RFM, scenario) ──> views.py (annotated Plotly) ──> app.py (tabs + filters)
```
- **Config-driven** (`config.py`): reads repo-root `.env.<ENV>` → project / dataset / creds.
  Nothing is hardcoded to one dataset.
- **Cached**: each query is written to `data/*.parquet`; the app is instant after first load
  and BigQuery cost is trivial. `make snapshot` bakes a self-contained offline image.
- **Honest about scope**: marketing / CAC / churn / NPS are **not** in the warehouse — the
  CAC panel is a clearly-labelled, editable *assumption*, not warehouse data.

## Quick start
```bash
make venv                 # Python 3.11 venv + deps
ENV=prod make run         # http://localhost:8050   (reads ../../.env.prod + ../../secrets/)
```
- Local deployment: [`notes/setup.local.md`](notes/setup.local.md)
- Production (Cloud Run): [`notes/setup.prod.md`](notes/setup.prod.md)

> Data note: `olist_gold_mart_prod` lives in BigQuery location **US**, project
> `sctp-team2-project2-elt` (1 `fact_orders` + `dim_customers/products/sellers/reviews`).
