# Refactor Plan

## Phase 1 — Naming standardization

**Canonical names (sctp-team2-project2 / olist_*):**

| Resource | Standard | Replaces |
|---|---|---|
| GCP project | `sctp-team2-project2-elt` | `mainitexp1`, `dsai-project-496504` |
| Bronze dataset | `olist_bronze` (dev: `olist_bronze_dev`, prod: `olist_bronze`) | `olin_bronze_dev_jun`, `raw_commerce` |
| Stage dataset | `olist_stage` / `olist_stage_dev` | `stage` schema in `brazil_ecommerce_proj` |
| Gold dataset | `olist_gold_mart` / `olist_gold_mart_dev` | `gold_mart` in `brazil_ecommerce_proj` |
| GCS bucket | `olist-elt-<env>` | (TBD if used) |
| SA keyfile | `./secrets/sctp-team2-project2-elt-*.json` (glob-resolve) | mixed absolute/relative paths |
| BQ location | `asia-southeast1` (confirm with you) | mixed `US`/`asia-southeast1` |

## Phase 2 — `.env.dev` and `.env.prod`

Add at repo root: `.env.dev`, `.env.prod`, `.env.example` (and update `.gitignore`).

```
GCP_PROJECT=sctp-team2-project2-elt
GOOGLE_APPLICATION_CREDENTIALS=./secrets/sctp-team2-project2-elt-1853e88c8665.json
BQ_LOCATION=asia-southeast1
BQ_BRONZE_DATASET=olist_bronze_dev    # _dev in dev, no suffix in prod
BQ_STAGE_DATASET=olist_stage_dev
BQ_GOLD_DATASET=olist_gold_mart_dev
DBT_TARGET=dev                        # prod in prod
MELTANO_ENVIRONMENT=dev
```

Files to convert to env-var refs:
- `p1_el/meltano-raw-csv/meltano.yml` — `project: ${GCP_PROJECT}`, `dataset: ${BQ_BRONZE_DATASET}`
- `p3_dbt_project/brazil_ecommerce/profiles.yml` — both `dev` and `prod` targets reading env vars
- `p6_orchestration/.../assets.py` — replace hardcoded `BQ_PROJECT`/`BQ_DATASET`/`BQ_LOCATION` with `os.getenv(...)`
- `p3_dbt_project/brazil_ecommerce/models/stage/sources.yml` — `database: "{{ env_var('GCP_PROJECT') }}"`, schema from env

## Phase 3 — Fix stg folder (1-to-1 dedup)

**Target structure** under `p3_dbt_project/brazil_ecommerce/models/stage/`:

```
sources.yml                        (Brazil_ecommerce dataset)
stg_customers.sql                  dedup from source olist_customers_dataset
stg_orders.sql                     dedup from olist_orders_dataset
stg_order_items.sql                dedup from olist_order_items_dataset
stg_order_payments.sql             dedup from olist_order_payments_dataset
stg_order_reviews.sql              dedup from olist_order_reviews_dataset
stg_products.sql                   dedup from olist_products_dataset
stg_product_category_translation.sql
stg_sellers.sql                    dedup from olist_sellers_dataset
stg_geolocation.sql                dedup from olist_geolocation_dataset
schema.yml
```

Each `stg_*.sql` is purely: `SELECT * FROM {{ source(...) }} QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY <updated_col or 1>) = 1` — no joins, no business logic.

**Deletes:** all current `fact_orders_stage*.sql`, all `dim_*` and `*_clean.sql` under `stage/stage_star/`. The whole `stage/stage_star/` directory goes away.

## Phase 4 — Move fact/dim build to `gold_mart`

Under `p3_dbt_project/brazil_ecommerce/models/gold_mart/`:

```
dim_customers.sql        ← from stg_customers
dim_sellers.sql          ← stg_sellers + stg_geolocation (zip join, current logic)
dim_products.sql         ← stg_products + stg_product_category_translation (drop the order_items join — that belongs in fact)
dim_reviews.sql          ← stg_order_reviews
fact_orders.sql          ← stg_orders + stg_order_items + stg_order_payments (current fact_orders_stage logic + null-id filters from commits c61bea9/1658304)
schema.yml               ← tests: not_null PKs, unique PKs, relationships fact→dim
```

`dbt_project.yml` updates:
```yaml
models:
  brazil_ecommerce:
    stage:    { +materialized: view,  +schema: stage }
    gold_mart:{ +materialized: table, +schema: gold_mart }
```

(Switching stg to `view` is the standard pattern since dedup is cheap and saves storage; flag if you'd rather keep `table`.)

## Phase 5 — Wire p6 dagster to materialize stg and mart

In `p6_orchestration/olist_orchestration/olist_orchestration/assets.py`:

1. Replace the single `dbt_models()` multi-asset using `dbt.cli(["build"])` with **dbt asset definitions** via `@dbt_assets(manifest=...)` so each model is an individually-materializable Dagster asset and the dag visualizes stg→gold_mart dependencies.
2. Move `BQ_PROJECT`/`BQ_DATASET`/`BQ_LOCATION` to `os.getenv(...)` with `.env.dev` loaded via `python-dotenv` in `definitions.py`.
3. Add a **job** `olist_full_refresh` = `bronze_raw_commerce` → all `stg_*` dbt assets → all gold_mart dbt assets; and two narrower jobs `stg_only` and `gold_mart_only` selecting by dbt tag.
4. Tag dbt models in `dbt_project.yml` (`tags: ['stage']` / `tags: ['gold_mart']`) so Dagster can select them.

## Phase 6 — Local + GCP deploy

- **Local dev**: `cp .env.dev .env && source .env && dagster dev` from `p6_orchestration/olist_orchestration/`. Add a `Makefile` at repo root with `make dev`, `make prod`, `make dbt-build`, `make meltano-run`.
- **Prod / GCP**: containerize p6 with a `Dockerfile` (python 3.11 + dagster + dbt-bigquery + meltano) and document deploy to **Cloud Run jobs** (cron-triggered) reading `.env.prod` via Secret Manager. Service account keyfile mounted from Secret Manager — not baked into image.

## Files I'd touch (count: ~25)

- **Create**: `.env.dev`, `.env.prod`, `.env.example`, `Makefile`, `p6_orchestration/.../Dockerfile`, 9 new `stg_*.sql`, 5 new `gold_mart/*.sql`, 2 schema.yml
- **Modify**: `meltano.yml`, dbt `profiles.yml` + `dbt_project.yml` + `sources.yml`, p6 `assets.py` + `definitions.py` + `resources.py` + `pyproject.toml`, `.gitignore`, root `readme.md`
- **Delete**: 10 files under `models/stage/` + `models/stage/stage_star/`, old `gold_mart/fact_orders.sql` (empty)

## Open questions before I touch code

1. **BQ location** — `US` (p6) or `asia-southeast1` (HoongJun .env)? Pick one.
2. **Stage materialization** — `view` (recommended) or keep `table`?
3. **Other teammates' configs** — `my-work/HoongJun/...` has its own meltano + .env. Standardize those too, or leave as personal sandboxes?
4. **Prod deploy target** — Cloud Run jobs, Composer (Airflow), or GKE? I assumed Cloud Run jobs.
5. **Bucket** — is GCS actually used, or does meltano go CSV→BQ direct? (Affects whether we need bucket naming.)

---

## Current-state inventory (from exploration)

### Secrets & GCP

- Service account: `sctp-team2-project2-elt@sctp-team2-project2-elt.iam.gserviceaccount.com`
- Keyfile: `secrets/sctp-team2-project2-elt-1853e88c8665.json`
- Hardcoded references found:
  - `p6_orchestration/olist_orchestration/olist_orchestration/assets.py:13` — `BQ_PROJECT = "sctp-team2-project2-elt"`
  - `p6_orchestration/olist_orchestration/olist_orchestration/assets.py:14` — `BQ_DATASET = "olin_bronze_dev_jun"`
  - `my-work/HoongJun/dev/p1_el/meltano-raw-csv/meltano.yml:33–34` — `project: sctp-team2-project2-elt`, `dataset: olin_bronze_dev_jun`
  - `p3_dbt_project/brazil_ecommerce/models/stage/sources.yml:5` — `database: mainitexp1` (other teammate's project)
  - `p3_dbt_project/brazil_ecommerce/profiles.yml:7,13` — `brazil_ecommerce_proj`, `mainitexp1`
- Mixed BQ locations: `US` (p6) vs `asia-southeast1` (HoongJun .env)

### dbt stage models (current)

`p3_dbt_project/brazil_ecommerce/models/stage/`:
- `fact_orders_stage.sql` — joins orders + order_items + order_payments with NOT NULL filters on ids
- `fact_orders_stage_clean.sql` — dedupes the above (ROW_NUMBER on order_purchase_timestamp DESC)

`p3_dbt_project/brazil_ecommerce/models/stage/stage_star/`:
- `dim_customers.sql` / `_clean.sql`
- `dim_products.sql` / `_clean.sql` (with order_items join — out of place for a dim)
- `dim_reviews.sql` / `_clean.sql`
- `dim_sellers.sql` / `_clean.sql` (with geolocation join)

All `_clean.sql` call `dbt_utils.deduplicate` on the non-clean. All materialized as `table` in `stage` schema.

### dbt gold_mart (current)

- `fact_orders.sql` — **empty file (0 bytes)**

### p6 dagster (current)

- `assets.py` — two multi_assets:
  - `bronze_raw_commerce()` — runs `meltano --environment=dev run tap-csv target-bigquery` (cwd = `my-work/HoongJun/dev/p1_el/meltano-raw-csv`), verifies CSV row counts vs BQ
  - `dbt_models()` — runs `dbt.cli(["build"])` once; no per-model assets, no stage/mart split
- `resources.py` — `DbtProject(project_dir=p3_dbt_project)` with `prepare_if_dev()`; `DbtCliResource`
- Hardcoded BQ_PROJECT / BQ_DATASET / BQ_LOCATION at module top

### Config files inventory

| Path | Hardcoded | Env-var refs |
|---|---|---|
| `my-work/HoongJun/dev/p1_el/meltano-raw-csv/.env` | absolute keyfile path | — |
| `my-work/HoongJun/dev/p1_el/meltano/.env` | relative keyfile path | `GCP_PROJECT=dsai-project-496504`, `BQ_DATASET=raw_commerce`, `BQ_LOCATION=asia-southeast1` |
| `my-work/HoongJun/dev/p1_el/webapp/.env` | keyfile | `GCP_PROJECT=dsai-project-496504`, `FLASK_SECRET`, etc. |
| `p1_el/meltano-raw-csv/meltano.yml` | `project: sctp-team2-project2-elt`, `dataset: olin_bronze_dev_jun` | — |
| `p3_dbt_project/brazil_ecommerce/profiles.yml` | `project: mainitexp1`, `dataset: brazil_ecommerce_proj` | — |
| `p3_dbt_project/brazil_ecommerce/dbt_project.yml` | schema/dataset hardcoded | — |
