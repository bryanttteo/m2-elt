# Local setup — rerun the Olist ELT pipeline

Get the pipeline running on your machine: **bronze (CSV → BigQuery) → dbt stage views
→ dbt gold tables**, optionally orchestrated by Dagster.

Verified toolchain (conda env named `dagster`): Python 3.11, dbt-core 1.10 +
dbt-bigquery, dagster 1.12, meltano 4.0, Google Cloud SDK (`bq`/`gcloud`).

---

## 0. Prerequisites
- **git**, **conda** (Miniconda/Anaconda), **Google Cloud SDK** (`gcloud`, `bq`).
- Access to GCP project **`sctp-team2-project2-elt`** (BigQuery Data Editor + Job User).
- The service-account keyfile **`sctp-team2-project2-elt-1853e88c8665.json`**
  (from the team vault — it is git-ignored, never commit it).

## 1. Clone and enter the repo
```bash
git clone <repo-url> && cd m2-elt
```

## 2. Secrets + env
```bash
mkdir -p secrets
cp /path/to/sctp-team2-project2-elt-1853e88c8665.json secrets/   # from the vault

cp .env.example .env.dev        # defaults already point at the canonical names
# .env.dev sets: GCP_PROJECT, GOOGLE_APPLICATION_CREDENTIALS=./secrets/...,
# BQ_LOCATION=US, BQ_BRONZE/STAGE/GOLD datasets (=_dev), OLIST_DATA_DIR=./datasets
```
> The dbt profile uses `method: oauth`, which reads `GOOGLE_APPLICATION_CREDENTIALS`.
> No `gcloud auth` is required if the keyfile is present. (If you'd rather use your own
> login: `gcloud auth application-default login` and leave the keyfile path unset.)

## 3. Create the conda env + install
```bash
conda create -n dagster python=3.11 -y
conda activate dagster

make install                    # installs the Dagster project + dagster-dbt,
                                # dbt-bigquery, google-cloud-bigquery, python-dotenv
pip install meltano             # only needed for the Meltano (alternative) load path

# sanity check the imports
python -c "import dotenv, dagster_dbt, google.cloud.bigquery, dbt.adapters.bigquery; print('deps OK')"
```
> If `import dotenv` fails, run `pip install python-dotenv` (some pip resolvers skip it).

## 4. Get the raw CSVs into `datasets/`
The pipeline loads from `datasets/` by default. If the folder is empty, pull from GCS:
```bash
gsutil -m cp 'gs://m2_olin_raw/*.csv' datasets/
# (or copy the 9 olist_*.csv + product_category_name_translation.csv in by hand)
```

## 5. Run it

### Option A — Dagster UI (recommended; runs the whole DAG)
```bash
make dev                        # Dagster UI at http://localhost:3000
```
In the UI, materialize the job **`olist_full_refresh`**: it loads bronze, then builds
the stage views and gold tables in dependency order. Narrower jobs: **`stg_only`**,
**`gold_mart_only`**.

### Option B — CLI, step by step
```bash
# 5b-i. Load bronze from datasets/ (uses the real loader functions)
cd p6_orchestration/olist_orchestration
python -c "
from olist_orchestration import config, assets
c = assets._bq_client()
for t, fn in config.CSV_FILES.items():
    assets._load_csv_to_bq(c, t, config.OLIST_DATA_DIR / fn)
    print('loaded', t)
"
cd ../..

# 5b-ii. Build + test the dbt models against BigQuery
make dbt-build ENV=dev          # = dbt deps + dbt build (stage views + gold tables)
make dbt-test  ENV=dev          # run just the tests
```

### Option C — Meltano load path instead of manual
```bash
export BRONZE_LOAD_METHOD=meltano
cd p1_el/meltano-raw-csv && make setup && make run   # tap-csv -> target-bigquery
```

## 6. Verify
A successful full run produces (in project `sctp-team2-project2-elt`):
- **`olist_bronze_dev`** — 9 raw tables (`olist_*_raw`, row counts == CSV records).
- **`olist_stage_dev`** — 9 `stg_*` **views**.
- **`olist_gold_mart_dev`** — `fact_orders` + `dim_customers/sellers/products/reviews`
  **tables**.
- `dbt build` ends with `PASS=51 ... ERROR=0` (14 models + 37 tests).

```bash
bq --project_id=sctp-team2-project2-elt ls olist_gold_mart_dev
```

## 7. Personal sandbox (`.env.<name>`)
To avoid clobbering the shared `_dev` datasets, work in your own datasets via the
**`.env.<name>`** convention. Replace `your_name` below with your own (e.g. `jun`,
`charmaine`). Copy `.env.dev`, give the datasets a personal suffix, then select it with
`ENV` / `OLIST_ENV`:
```bash
cp .env.dev .env.your_name     # then edit: BQ_*_DATASET=olist_*_your_name
make dev       ENV=your_name    # Dagster on your own datasets
make dbt-build ENV=your_name    # dbt build into your own datasets
```

**Shortcut — `make <name>`:** the Makefile auto-creates a target for each `.env.<name>`
file, so `make <name>` is just `make dev ENV=<name>`:
```bash
make your_name                  # == make dev ENV=your_name
```
`make help` lists the personal envs it detected. The connection (project, keyfile,
location, dbt target) is identical to dev — only the datasets differ. `.env.<name>`
files are git-ignored.

## 8. Prod
Set `ENV=prod` / `OLIST_ENV=prod` (uses `.env.prod` → unsuffixed datasets) and deploy the
container per `p6_orchestration/olist_orchestration/DEPLOY.md` (Cloud Run jobs + Secret Manager).

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `No module named 'dotenv'` | `pip install python-dotenv` in the `dagster` env |
| `command not found: dbt-build` | it's a make target: run `make dbt-build` |
| dbt `Could not find profile` | run from repo root via `make`, or pass `--profiles-dir .` inside `p3_dbt_project/brazil_ecommerce` |
| `Missing close quote` on load | ensure `allow_quoted_newlines=True` (already set) — see `notes/issues.md` |
| `string_field_0/1` columns | all-text file; the loader's explicit-schema path handles it — see `notes/issues.md` |
| BigQuery auth errors | confirm `secrets/*.json` exists and `GOOGLE_APPLICATION_CREDENTIALS` resolves (it's made absolute at runtime) |
