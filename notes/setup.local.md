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

### 2a. Service-account keyfile

Check if the keyfile already exists:
```bash
ls secrets/sctp-team2-project2-elt-1853e88c8665.json
```

If it's **missing**, download it from the team Google Drive:
> **Google Drive → SCTP Team2 → keys → `sctp-team2-project2-elt-1853e88c8665.json`**

Then place it in the repo:
```bash
mkdir -p secrets
cp ~/Downloads/sctp-team2-project2-elt-1853e88c8665.json secrets/
```

> **Never commit this file** — it is git-ignored.

### 2b. Environment file

Check if `.env.dev` already exists:
```bash
ls .env.dev
```

If it's **missing**:
1. Check the team Google Drive first — a pre-filled `.env.dev` may already be there:
   > **[Google Drive → SCTP Team2 → keys](https://drive.google.com/drive/u/1/folders/16cAsp_Pcq10lgHRpRnOQkW1scUHejuGe)**
   >
   > Download `.env.dev` from there and copy it to the repo root.

2. If there's no `.env.dev` in Drive, create one from the example:
   ```bash
   cp .env.example .env.dev
   ```
   Then open `.env.dev` and confirm these values:
   ```dotenv
   GCP_PROJECT=sctp-team2-project2-elt
   GOOGLE_APPLICATION_CREDENTIALS=./secrets/sctp-team2-project2-elt-1853e88c8665.json
   BQ_LOCATION=US
   BQ_BRONZE_DATASET=olist_bronze_dev
   BQ_STAGE_DATASET=olist_stage_dev
   BQ_GOLD_DATASET=olist_gold_mart_dev
   OLIST_DATA_DIR=./datasets
   ```

> The dbt profile uses `method: oauth`, which reads `GOOGLE_APPLICATION_CREDENTIALS`.
> No `gcloud auth` is required if the keyfile is present. (If you'd rather use your own
> login: `gcloud auth application-default login` and leave the keyfile path unset.)

> **Verify:** `cat .env.dev` shows the values above and `ls secrets/*.json` shows the keyfile.

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

> **Verify:** `deps OK` printed with no errors.

## 4. Get the raw CSVs into `datasets/`
The pipeline loads from `datasets/` by default. If the folder is empty, pull from GCS:
```bash
gsutil -m cp 'gs://m2_olin_raw/*.csv' datasets/
# (or copy the 9 olist_*.csv + product_category_name_translation.csv in by hand)
```

> **Verify:** `ls datasets/*.csv | wc -l` should show **10** files (9 olist_* + category translation).

## 5. Run it

### Option A — Dagster UI (recommended; runs the whole DAG)
```bash
make dev                        # Dagster UI at http://localhost:3000
```
In the UI, materialize the job **`olist_full_refresh`**: it loads bronze, then builds
the stage views and gold tables in dependency order. Narrower jobs: **`stg_only`**,
**`gold_mart_only`**.

> **Verify (Dagster UI):** After materializing, go to **Assets** — all assets should show
> a green tick. Any failure shows red; click the asset to see logs.

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
```

> **Verify (BigQuery):** Open [BigQuery Console](https://console.cloud.google.com/bigquery) →
> project `sctp-team2-project2-elt` → dataset `olist_bronze_dev`. You should see 9 tables
> (`olist_*_raw`). Click any table → **Preview** to confirm rows loaded.

```bash
# 5b-ii. Build + test the dbt models against BigQuery
make dbt-build ENV=dev          # = dbt deps + dbt build (stage views + gold tables)
make dbt-test  ENV=dev          # run just the tests
```

> **Verify (BigQuery):** Check datasets `olist_stage_dev` (9 views) and `olist_gold_mart_dev`
> (5 tables: `fact_orders` + 4 `dim_*`). Terminal output should end with
> `PASS=51 ... ERROR=0`.

### Option C — Meltano load path instead of manual
```bash
export BRONZE_LOAD_METHOD=meltano
cd p1_el/meltano-raw-csv && make setup && make run   # tap-csv -> target-bigquery
```

> **Verify (BigQuery):** Same as Option B step i — check `olist_bronze_dev` for 9 tables.

## 6. Verify end-to-end
A successful full run produces (in project `sctp-team2-project2-elt`):
- **`olist_bronze_dev`** — 9 raw tables (`olist_*_raw`, row counts == CSV records).
- **`olist_stage_dev`** — 9 `stg_*` **views**.
- **`olist_gold_mart_dev`** — `fact_orders` + `dim_customers/sellers/products/reviews`
  **tables**.
- `dbt build` ends with `PASS=51 ... ERROR=0` (14 models + 37 tests).

```bash
# Quick CLI check
bq --project_id=sctp-team2-project2-elt ls olist_bronze_dev
bq --project_id=sctp-team2-project2-elt ls olist_stage_dev
bq --project_id=sctp-team2-project2-elt ls olist_gold_mart_dev
```

> **Verify (Dagster UI):** Go to **Jobs → `olist_full_refresh` → Runs** — the latest run
> should show **SUCCESS** (green). Click into it to see per-asset timing and logs.

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

> For prod deployment (GCE VM + Docker + nginx auth proxy), see **[`notes/setup.prod.md`](setup.prod.md)**.
> Do not follow the steps in this file for prod — dataset names, config files, and the
> deploy process are different.

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
