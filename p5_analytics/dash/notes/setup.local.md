# Local setup — Olist executive dashboard

Run the Plotly Dash dashboard on your machine against the `olist_gold_mart_prod` gold mart.

Verified toolchain: **Python 3.11** (dash 2.18, dash-mantine-components 0.14, plotly 5.24,
google-cloud-bigquery 3.27). dmc 0.14 requires React 18 — `app.py` sets that automatically.

---

## 0. Prerequisites
- **Python 3.11** (`python3.11`). 3.14 has no wheels for the pinned `pyarrow`; use 3.11.
- Read access to BigQuery project **`sctp-team2-project2-elt`** (BigQuery Job User +
  Data Viewer on `olist_gold_mart_prod`).
- The service-account keyfile in the repo's `secrets/` (git-ignored) — same one the rest
  of the pipeline uses.

## 1. Config (from the repo root)
The dashboard reads the **repo-root `.env.<ENV>`** (default `ENV=prod`) for project /
dataset / credentials — the same convention as the pipeline. Confirm `.env.prod` has:
```dotenv
GCP_PROJECT=sctp-team2-project2-elt
BQ_LOCATION=US
BQ_GOLD_DATASET=olist_gold_mart_prod
GOOGLE_APPLICATION_CREDENTIALS=./secrets/<your-sa-key>.json   # or use ADC (see below)
```
> The path may be relative to the repo root — `config.py` makes it absolute. On Cloud Run
> you leave it unset and rely on the attached service account.
>
> No keyfile? Use your own login instead: `gcloud auth application-default login` and leave
> `GOOGLE_APPLICATION_CREDENTIALS` unset.

## 2. Install
```bash
cd p5_analytics/dash
make venv            # creates .venv (Python 3.11) and installs requirements.txt
```
> Verify: `.venv/bin/python -c "import dash, dash_mantine_components; print('ok')"`.

## 3. Run
```bash
ENV=prod make run            # http://localhost:8050
# or: ENV=prod .venv/bin/python app.py
```
First load runs two BigQuery queries (~seconds) and caches them to `data/*.parquet`; every
load after that is instant. Use a different env with `ENV=dev make run` (reads `.env.dev`).

> **Verify:** the page title is "Olist · Executive Dashboard", the KPI cards show
> GMV ≈ R$13.6M / 99,441 orders / 3.1% repeat rate, and the date-range + state filters
> update every chart. All four tabs should render (overview, retention, delivery, diagnosis).

## 4. Refresh / snapshot the data
```bash
ENV=prod make snapshot       # re-query BigQuery and overwrite data/*.parquet
```
Run this when the gold mart is rebuilt. To preview the fully-offline (no-BigQuery) mode the
demo image uses:
```bash
DASH_OFFLINE=1 ENV=prod make run
```

## 5. Sanity-check the numbers (optional)
```bash
bq --location=US query --use_legacy_sql=false \
 'WITH o AS (SELECT id, SUM(price) g FROM `sctp-team2-project2-elt.olist_gold_mart_prod.fact_orders`
             WHERE order_purchase_timestamp IS NOT NULL GROUP BY id)
  SELECT ROUND(SUM(g)) gmv, COUNT(*) orders FROM o'
# expect gmv ≈ 13,591,644 and orders = 99,441 (matches the KPI cards)
```

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `r.useId is not a function` (blank page, JS error) | React-18 not set — ensure `app.py` runs `_set_react_version("18.2.0")` before importing dmc (already in place). |
| `data type 'dbdate' not understood` on cache read | `bq.py` must `import db_dtypes`; reinstall `db-dtypes`. |
| `Failed building wheel for pyarrow` | You're on Python 3.14. Recreate the venv with `python3.11`. |
| `Dataset ... not found in location US` | The gold mart isn't materialized / wrong location. Build it: `make dbt-build ENV=prod` at the repo root (stage_prod already exists), then retry. |
| `Address already in use` (port 8050) | `lsof -ti:8050 \| xargs kill -9`, then rerun. |
| BigQuery auth errors | Confirm `secrets/*.json` exists and `GOOGLE_APPLICATION_CREDENTIALS` resolves, or run `gcloud auth application-default login`. |

> For production (Cloud Run), see **[`setup.prod.md`](setup.prod.md)**.
