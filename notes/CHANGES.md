# Change log — ELT refactor (plan/plan1.md execution)

Executed `plan/plan1.md` end-to-end and validated against live BigQuery
(`sctp-team2-project2-elt`, location `US`) using the `dagster` conda env.
Final state: `dbt build` → **PASS=51, ERROR=0, SKIP=0** (14 models + 37 tests).

## Decisions locked in
- **BQ location:** `US`
- **Stage materialization:** `view`
- **Teammate configs** (`my-work/HoongJun/*`): left as personal sandboxes
- **Bronze load:** manual from `datasets/*.csv` is primary; Meltano kept as an
  interchangeable alternative (`BRONZE_LOAD_METHOD=meltano`)

## Canonical naming
| Resource | Value (dev / prod) |
|---|---|
| GCP project | `sctp-team2-project2-elt` |
| Bronze dataset | `olist_bronze_dev` / `olist_bronze` |
| Stage dataset | `olist_stage_dev` / `olist_stage` |
| Gold dataset | `olist_gold_mart_dev` / `olist_gold_mart` |
| Bronze tables | `olist_*_raw` (raw layer; both load paths agree) |
| SA keyfile | `./secrets/sctp-team2-project2-elt-*.json` |

## Phase 1+2 — naming + env
- Added `.env.example` (committed), `.env.dev`, `.env.prod`; `.gitignore` now
  un-ignores `**/.env.example` and ignores dbt/dagster/meltano build artifacts.
- Env-var-ised: `p1_el/meltano-raw-csv/meltano.yml` (`${GCP_PROJECT}` etc.), its
  `.env` (keyfile repointed to `./secrets/`) and `Makefile`; dbt `profiles.yml`
  (dev+prod, `method: oauth` works for SA key *and* gcloud ADC), `sources.yml`,
  `dbt_project.yml`.
- **Bug fixed:** `dbt_project.yml` keyed models under `brazil_ecommerce_proj`
  (≠ project name `brazil_ecommerce`), silently disabling every model config.
- Added `macros/generate_schema_name.sql` so `+schema` becomes the dataset name
  verbatim instead of dbt's `<target>_<schema>` concatenation.

## Phase 3 — stage layer (1:1 dedup)
- Created 9 `stg_*.sql` (pure `SELECT * … QUALIFY ROW_NUMBER() = 1`), new
  `schema.yml` with PK unique/not_null tests.
- Deleted `fact_orders_stage*.sql` and the whole `stage/stage_star/` directory.

## Phase 4 — gold_mart star schema
- `fact_orders` (former stage join + clean dedup + null-id filters), `dim_customers`,
  `dim_sellers` (zip join), `dim_products` (order-items join removed — moved to fact),
  `dim_reviews`.
- `schema.yml`: PK unique/not_null, fact→dim relationships, accepted_values for
  `order_status` / `payment_type`. Generic-test args nested under `arguments:`
  (dbt 1.10 requirement).
- `dbt_project.yml`: stage = view + tag `stage`; gold_mart = table + tag `gold_mart`;
  datasets from env vars.

## Phase 5 — Dagster (p6)
- New `config.py`: loads repo-root `.env.<OLIST_ENV>` via python-dotenv, resolves a
  relative keyfile to absolute.
- **Bug fixed:** `resources.py` `DBT_DIR` pointed at `p3_dbt_project` instead of
  `p3_dbt_project/brazil_ecommerce` (no `dbt_project.yml` one level up).
- Bronze `multi_asset` keys = `["brazil_ecommerce", table]` so they wire straight
  into the dbt source assets dagster-dbt derives.
- Bronze loads from `datasets/` (manual) or Meltano via `BRONZE_LOAD_METHOD`.
- Jobs `olist_full_refresh` / `stg_only` / `gold_mart_only` select dbt assets by tag.
- `pyproject.toml`: added dagster-dbt, dbt-bigquery, google-cloud-bigquery, python-dotenv.

## Phase 6 — local + deploy
- Root `Makefile` (`install`/`dev`/`prod`/`dbt-build`/`dbt-test`/`meltano-run`).
- `Dockerfile` + `.dockerignore` + `DEPLOY.md` (Cloud Run jobs + Secret Manager).
- Updated `readme.md` with an "Implemented V1" section.

## Loader fixes found by the live run (`assets.py::_load_csv_to_bq`)
- **`allow_quoted_newlines=True`** — `olist_order_reviews_dataset.csv` has embedded
  newlines inside quoted review comments; the load failed without this.
- **All-text schema naming** — `product_category_name_translation.csv` is all-text
  with a UTF-8 BOM, so BigQuery autodetect produced `string_field_0/1`. Added
  `_is_all_text()` / `_csv_header()`: all-text files now get an explicit STRING
  schema named from the (BOM-stripped) header, so the manual and Meltano paths
  produce identical column names. Typed files still use autodetect.

## Verified
- Bronze: all 9 tables loaded, row counts == CSV record counts exactly.
- dbt: `parse` (deprecation-free), `compile`, and full `build` all pass against BQ.

## Follow-ups
- **Standardized `olist_` dataset naming** — bronze dataset is `olist_bronze_<env>`
  (dev `olist_bronze_dev`, prod `olist_bronze`, jun `olist_bronze_jun`), consistent with
  `olist_stage_*` / `olist_gold_mart_*`. The dbt **source name** stays `brazil_ecommerce`
  (logical, used only in `source()` calls + the project/profile name); bronze tables stay
  `olist_*_raw`.
- **Dagster asset keys** via `OlistDbtTranslator`: keyed by medallion layer + env
  (from `OLIST_ENV`) — `olist_bronze_<env>/<table>`, `olist_stage_<env>/<model>`,
  `olist_gold_mart_<env>/<model>` — so dev/prod/jun runs appear as distinct assets
  (e.g. `olist_stage_dev/stg_orders`, `olist_stage_prod/stg_orders`). Bronze multi_asset
  + dbt sources share `olist_bronze_<env>` so bronze→stg stays wired within a run.
- **Personal sandboxes** via the `.env.<name>` convention (`.env.jun` added). Same
  project/keyfile/connection as dev, isolated `_<name>` datasets. Select with
  `ENV=<name>` / `OLIST_ENV=<name>`; the Makefile auto-generates a `make <name>` target
  per `.env.<name>` file. Verified end-to-end: `olist_bronze_jun` / `olist_stage_jun` /
  `olist_gold_mart_jun` built green (PASS=51).
- **Makefile bug (macOS make 3.81)**: `.ONESHELL:` is ignored on the GNU make 3.81 that
  ships with macOS, so each recipe line ran in a separate shell and the sourced
  `.env.<ENV>` vars were lost before `dbt` ran — `dbt-build ENV=jun` silently built into
  the dev datasets (masked because env_var defaults == dev). Fixed by writing the dbt
  recipes as a single `; \`-continued shell invocation instead of relying on `.ONESHELL`.

## Open / assumed
- Prod deploy target assumed **Cloud Run jobs** (see `DEPLOY.md`); swap for
  Composer/GKE changes only the deploy commands.
- FK relationship tests are `error` severity (currently all pass on this data).
