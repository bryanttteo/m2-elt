# Olist — Executive Dashboard (Apache Superset)

A management-facing BI dashboard over the gold mart
(`sctp-team2-project2-elt.olist_gold_mart_prod`). It tells **one connected story** for the
CEO, CMO and CTO — the same narrative as the Plotly Dash sibling in `../dash/`, rebuilt on
Superset so the team can share, filter and extend it.

## The story (why this exists)

> **GMV is growing, but we're working harder to grow.** Growth is *bought* (new-customer
> acquisition), not *earned* (repeat). The **repeat-customer rate (~4%) is the binding
> constraint** — and the root cause is the **delivery experience**: late deliveries →
> low reviews → no reorder.

Each executive sees a symptom and misattributes the cause; the dashboard connects them:

| Tab | Audience | What it proves |
| --- | --- | --- |
| **1 · Executive** | CEO | Growth is acquisition-driven; repeat rate is the lever, not pricing/competition. |
| **2 · Retention** | CMO | It isn't weak brand loyalty — retention collapses after order 1, and reorder rate tracks the *review*. |
| **3 · Delivery & Reviews** | CTO | Late delivery is a **revenue leak**: review score falls monotonically with lateness (4.29★ → 1.69★) and low-review buyers don't return. |
| **4 · Catalog** | — | Supporting category mix. |

The chain is real in the data (validated against BigQuery): on-time orders average **4.29★**
vs **1.69★** for 8+ days late, and on-time buyers reorder at **3.4%** vs ~2.3% for late ones.

## Architecture

```
Superset (gunicorn)  ──SQLAlchemy──►  BigQuery  olist_gold_mart_prod
        │                              (auth via GOOGLE_APPLICATION_CREDENTIALS / ADC)
        ├── metadata  ──►  Postgres   (dashboards, charts, users)
        └── cache     ──►  Redis      (chart result cache; the cloud perf lever)
```

- **Semantic layer = Superset virtual datasets** (SQL in `sql/`), not pandas. Four datasets
  (`v_orders`, `v_customers`, `v_cohort_retention`, `v_category`) translate the pandas
  derivations in `../dash/metrics.py` into BigQuery SQL (window functions for order
  sequence / cohort, CASE buckets for delivery & review, RFM segment rules).
- **Everything is an importable asset bundle** — `bootstrap/build_bundle.py` generates a
  Superset `Dashboard` export ZIP from compact Python definitions with **deterministic
  UUIDs**, so re-imports update in place. No hand-clicking; the dashboard is git-tracked.

## Layout

```
superset/
├── docker-compose.yml          # superset + postgres + redis (+ one-shot init)
├── Dockerfile                  # apache/superset + sqlalchemy-bigquery
├── superset_config.py          # metadata DB, Redis caching, row limits, feature flags
├── .env.superset.example       # copy → .env.superset, set SUPERSET_SECRET_KEY
├── sql/                        # source-of-truth SQL for each virtual dataset
├── bootstrap/
│   ├── init.sh                 # db upgrade → admin → build bundle → import
│   └── build_bundle.py         # emits dist/olist_bundle.zip (datasets+charts+dashboard)
├── dist/                       # generated bundle (git-ignored)
└── notes/{setup.local.md, setup.prod.md}
```

## Quickstart (local)

```bash
cp .env.superset.example .env.superset      # then set SUPERSET_SECRET_KEY
docker compose up -d                         # builds, migrates, imports the bundle
open http://localhost:8088                    # login: team2 / password
```

Full walkthrough → [`notes/setup.local.md`](notes/setup.local.md).
Production options (Cloud Run vs separate VM) → [`notes/setup.prod.md`](notes/setup.prod.md).

## Using the dashboard

**Where / login**

| Environment | URL | Login |
| --- | --- | --- |
| Local | http://localhost:8088 | `team2` / `password` |
| Prod (Cloud Run) | https://olist-superset-513410438758.us-central1.run.app | `team2` / `password` |

After login, open **Dashboards → Olist — Executive Dashboard** (prod direct link:
`…/superset/dashboard/olist-executive/`).

**Navigate** — the four tabs are a narrative; present them in order:
1. **Executive (CEO)** — KPIs + GMV new-vs-repeat → *growth is bought, not earned; repeat rate is the constraint.*
2. **Retention (CMO)** — cohort/RFM/reorder-by-review → *it isn't weak brand loyalty; the first experience fails.*
3. **Delivery & Reviews (CTO)** — review-by-delivery + late-rate → *late delivery is the revenue leak (4.29★ → 1.69★).*
4. **Catalog** — supporting category mix.

**Filter** — the bar at the top of the dashboard has **Order month** (date range) and
**Customer state** (multi-select). Set them once and every chart on every tab updates. Clear
them to return to all-time / all-states.

**Refresh data** — charts are cached (~1h). To pull the latest from BigQuery, use the
dashboard **⋯ menu (top-right) → Force refresh**, or hover a single chart → its **⋯ → Force refresh**.

**Drill / explore a chart** — hover a chart → **⋯ → View as table** (see the numbers) or
**Edit chart** (opens Explore to change metrics/filters). Edits in the UI are for exploration;
to make them permanent see *Editing the dashboard reproducibly* below.

**Export** — chart **⋯ → Download → Export to CSV/Image**; dashboard **⋯ → Download → as Image / PDF**
for the deck.

**Presenting tip** — Superset has no kiosk flag here; for a clean screen use the browser's
full-screen (F11) and collapse the left nav. The dashboard is self-narrating (each tab opens
with a markdown verdict), so it reads as a slide deck.

## Editing the dashboard reproducibly

Change the SQL in `sql/` or the chart/dashboard definitions in `bootstrap/build_bundle.py`,
then re-run the import:

```bash
docker compose run --rm superset-init        # rebuilds bundle + re-imports (idempotent)
```

UI edits are fine for exploration, but the **bundle is the source of truth** — anything you
want to keep should go into `build_bundle.py` / `sql/` so it survives a clean rebuild.

> **Data contract:** consumes the gold mart only (never silver/raw), per
> `../README.md`. Marketing-spend / CAC figures are *not* in the warehouse; the unit-economics
> framing is shown as a labelled illustrative note, not as data.
