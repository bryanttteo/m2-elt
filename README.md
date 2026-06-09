# SCTP Team 2 — Project 2
## Olist E-Commerce: End-to-End Data & ML Platform (V1, on GCP)

An open **lakehouse** pipeline: raw CSVs → BigQuery Iceberg → dbt star schema (medallion) → quality gates → analytics, orchestrated by Dagster. Built on GCP managed services for V1; designed to migrate to on-prem OSS (see `MIGRATION.md`).

> **Folder naming:** top-level folders are prefixed `p1_`…`p7_` to show pipeline order. Inner folders (dbt `models/`, `macros/`, `.github/workflows/`, etc.) stay bare because the tools require those exact names.

### Implemented pipeline (V1, canonical naming)

> The medallion table below is the original design target. What is **wired and
> running today** uses the canonical names below. Config is driven by `.env.<env>`
> at repo root (copy from `.env.example`).

| Layer | BigQuery dataset (dev / prod) | Built by | Path |
|---|---|---|---|
| **Bronze** | `olist_bronze_dev` / `olist_bronze` | manual CSV load *or* Meltano | `p1_el/meltano-raw-csv/`, `datasets/` |
| **Stage** | `olist_stage_dev` / `olist_stage` | dbt views (`stg_*`, 1:1 dedup) | `p3_dbt_project/brazil_ecommerce/models/stage/` |
| **Gold mart** | `olist_gold_mart_dev` / `olist_gold_mart` | dbt tables (`fact_orders`, `dim_*`) | `…/models/gold_mart/` |

- **GCP project:** `sctp-team2-project2-elt` · **BQ location:** `US`
- **SA keyfile:** `./secrets/sctp-team2-project2-elt-*.json`
- **Orchestration:** Dagster (`p6_orchestration/olist_orchestration`) — jobs
  `olist_full_refresh`, `stg_only`, `gold_mart_only`. Deploy notes in that folder's `DEPLOY.md`.

### Architecture at a glance (medallion)

| Tier | Where (BigQuery) | Produced by | Folder |
|---|---|---|---|
| **Bronze** | `raw_commerce` | dlt / Meltano (EL) | `p1_el/bronze/` (tier docs) |
| **Silver** | `silver_commerce` | dbt (cleaned, conformed) | `p3_dbt_project/models/silver/` |
| **Gold** | `gold_commerce` (Iceberg) | dbt (marts) | `p3_dbt_project/models/gold/` |

### Pipeline flow
```
p1_el (dlt/Meltano)   →  BRONZE raw_commerce
                              │
p3 dbt silver         →  SILVER silver_commerce  (clean/type/conform)
                              │
p3 dbt gold           →  GOLD gold_commerce      (dim_/fct_/mart_, Iceberg)
                              │
p4_data_quality       →  tests gate the gold marts
                              │
p5_analytics          →  KPIs, charts, insights
                              │
p6_orchestration      →  Dagster runs the whole chain on a schedule
```

### Folder map (every folder has its own README)
| Folder | Module | Owner | Produces |
|---|---|---|---|
| `p1_el/` | M1 Ingestion | John / Bryan | bronze raw tables (dlt + meltano) |
| `p1_el/bronze/` | M1 (tier) | John / Bryan | bronze tier contract/docs |
| `p2_warehouse_design/` | M2 Design | Charmaine / Soon Meng | ERD + star schema spec |
| `p3_dbt_project/` | M3 ELT | **Hoong Jun** / Bryan | silver + gold models |
| `p3_dbt_project/models/silver/` | M3 | Hoong Jun / Bryan | silver_commerce.* |
| `p3_dbt_project/models/gold/` | M3 | Hoong Jun / Bryan | gold_commerce.* (Iceberg) |
| `p3_dbt_project/macros/cross_db/` | M3 | Hoong Jun | migration-seam macros |
| `p3_dbt_project/tests/` | M3/M4 | Charmaine / Jenn Fang | singular/custom tests |
| `p3_dbt_project/seeds/` | M3 | Hoong Jun / Bryan | static reference tables |
| `p4_data_quality/` | M4 QA | Charmaine / Jenn Fang | tests + QA report |
| `p5_analytics/` | M5 Analysis | John / Chun Wei | notebooks + insights |
| `p6_orchestration/` | M6 Orchestration | **Hoong Jun** / Soon Meng | Dagster pipeline |
| `.github/workflows/` | M6 | Hoong Jun / Soon Meng | scheduled trigger + CI (must stay at root) |
| `p7_docs/` | M7 Docs | All | report + deck + diagrams |

### Quick start
```bash
# 0. Config: copy the template and adjust if needed
cp .env.example .env.dev          # GCP project / datasets / keyfile path
gcloud config set project sctp-team2-project2-elt

# 1. Install the orchestration package (Dagster + dbt-bigquery + deps)
make install

# 2a. Run the whole pipeline interactively in Dagster (UI on :3000)
make dev                          # then materialize job `olist_full_refresh`

# 2b. …or run layers directly from the CLI
make dbt-build ENV=dev            # bronze must already be loaded
make meltano-run                  # optional: Meltano bronze load path
```
Bronze loads from `datasets/*.csv` by default (`BRONZE_LOAD_METHOD=manual`). Alternatives:
`BRONZE_LOAD_METHOD=meltano_csv` runs the Meltano tap-csv → target-bigquery path
(`p1_el/meltano-raw-csv`); `BRONZE_LOAD_METHOD=meltano_postgres` runs tap-postgres →
target-bigquery from Cloud SQL (`p1_el/olist-meltano-pg`). (`meltano` is a legacy alias
for `meltano_csv`.)

### Project conventions
- **Medallion naming:** silver = staging + intermediate combined (no separate staging folder); bronze = the raw dataset EL lands.
- **Folder order:** `p1_`…`p7_` prefixes encode pipeline sequence; inner tool folders stay bare.
- **dbt owns all writes** to silver/gold — never hand-write SQL into those datasets.
- **Models read one tier down only:** silver←bronze, gold←silver. Never skip a tier.
- **Migration seams** (dual-target profiles, dialect macros) are intentional — see `MIGRATION.md`.