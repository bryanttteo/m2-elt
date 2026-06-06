# olist_orchestration

This is a [Dagster](https://dagster.io/) project scaffolded with [`dagster project scaffold`](https://docs.dagster.io/guides/build/projects/creating-a-new-project).

## Getting started

First, install your Dagster code location as a Python package. By using the --editable flag, pip will install your Python package in ["editable mode"](https://pip.pypa.io/en/latest/topics/local-project-installs/#editable-installs) so that as you develop, local code changes will automatically apply.

```bash
pip install -e ".[dev]"
```

Then, start the Dagster UI web server:

```bash
dagster dev
```

Open http://localhost:3000 with your browser to see the project.

You can start writing assets in `olist_orchestration/assets.py`. The assets are automatically loaded into the Dagster code location as you define them.

## This project: Olist EL → dbt

Two assets in `assets.py`:
- **`bronze_raw_commerce`** (`multi_asset`, `compute_kind=meltano`) — shells out to Meltano
  (`tap-csv` → `target-bigquery`) to load the Olist CSVs into BigQuery dataset `olin_bronze_dev_jun`,
  then verifies each CSV's record count landed in its bronze table (counts shown as asset metadata).
- **`dbt_models`** (`@dbt_assets`) — runs `dbt build` on the `p3_dbt_project` (staging → marts).

**Run order matters:** materialize `bronze_raw_commerce` first, then the dbt assets
(there is no dependency edge between them — see learnings below).

## Fixes & learnings (debugging log)

Hard-won notes from getting this pipeline green. Each was a real failure.

### 1. A failed Dagster step only shows the *wrapper* error
The run log shows `subprocess.CalledProcessError ... returned non-zero exit status 1` — that's
just the asset re-raising. The **real** error (Meltano's stderr) is in the captured compute log:
```
<dagster_home>/storage/<run_id>/compute_logs/<step>.err
```
Always read that file, not just the red Dagster line.

### 2. Meltano cwd must contain `meltano.yml`
`p1_el` has **no** `meltano.yml` — the projects live in subdirs (`meltano-raw-csv/`).
Running Meltano with `cwd=p1_el` fails instantly. `MELTANO_DIR` must point at `p1_el/meltano-raw-csv`.

### 3. `target-bigquery` (z3z1ma) `storage_write_api` crashes on shutdown
It loaded all data fine, committed state, **then** crashed closing its streams:
`StreamClosedError: Cannot close again when the connection is already closed` (multiprocessing
workers double-closing). Non-zero exit → false Dagster failure.
**Fix:** switch the loader to `method: batch_job` (BigQuery load jobs — clean finalize).

### 4. The EL **appends** — re-runs duplicate data
`target-bigquery` appends; there is no upsert/merge key configured. Because the cosmetic crash (#3)
made us re-run, bronze ended up **2× duplicated** (and the old data was a partial 500-row sample).
**Options:** reset bronze before each load (`bq rm`/`bq mk`, see `p3_dbt_project` README), *or*
rely on the staging dedupe (every `stg_*` model dedupes by `_sdc_sequence`), keeping silver clean.

### 5. No auto-dependency between the Meltano asset and dbt sources
`bronze_raw_commerce` outputs keys `["raw_commerce", <table>]`; dbt source assets have different
keys, so Dagster won't order them. **Materialize bronze first, then dbt** — or wire a
`DagsterDbtTranslator` to map dbt sources onto the bronze keys.

### 6. Verifying "did the whole CSV load?" — don't use `wc -l`
`order_reviews` comments contain embedded newlines, so physical lines ≠ records. The asset counts
CSV **records** with `csv.reader` (handles quoted multiline fields) and compares to `COUNT(*)` in
BigQuery, logging `✅ exact / ⚠️ appended / ❌ MISSING ROWS` per table.

### 7. dbt dataset names are verbatim
`p3_dbt_project` uses a `generate_schema_name` override so `+dataset` values are used as-is
(`olin_silver_dev_jun`, not `<target>_olin_silver_dev_jun`). Everything is in BigQuery location **US**.

## Development

### Adding new Python dependencies

You can specify new Python dependencies in `setup.py`.

### Unit testing

Tests are in the `olist_orchestration_tests` directory and you can run tests using `pytest`:

```bash
pytest olist_orchestration_tests
```

### Schedules and sensors

If you want to enable Dagster [Schedules](https://docs.dagster.io/guides/automate/schedules/) or [Sensors](https://docs.dagster.io/guides/automate/sensors/) for your jobs, the [Dagster Daemon](https://docs.dagster.io/guides/deploy/execution/dagster-daemon) process must be running. This is done automatically when you run `dagster dev`.

Once your Dagster Daemon is running, you can start turning on schedules and sensors for your jobs.

## Deploy on Dagster+

The easiest way to deploy your Dagster project is to use Dagster+.

Check out the [Dagster+ documentation](https://docs.dagster.io/dagster-plus/) to learn more.
