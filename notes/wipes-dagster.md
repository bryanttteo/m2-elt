# Wiping Dagster materializations / history

How to clear the "Materialized" markers in the Dagster Asset catalog so assets show
**"Never materialized"** again and you can re-run a clean pipeline.

> What this affects: **only Dagster's local metadata** (run history, event/compute logs,
> asset materialization records). It does **not** touch BigQuery data, code, or dbt models.

All commands run from the Dagster project dir (the one containing `pyproject.toml` / `assets.py`):
```bash
cd p6_orchestration/olist_orchestration
conda activate dagster
```

## Where it's stored
Dagster keeps everything under `$DAGSTER_HOME`. If `DAGSTER_HOME` is **unset**, `dagster dev`
creates a temporary instance dir named `.tmp_dagster_home_*` in the project dir — that's where
the history lives.

## Option A — wipe materializations only (keep run history)
Run in a second terminal while `dagster dev` is still up. Point the CLI at the SAME instance
`dagster dev` is using (the newest temp home), then wipe:
```bash
export DAGSTER_HOME="$PWD/$(ls -dt .tmp_dagster_home_* | head -1)"
dagster asset wipe --all          # confirm when prompted
```
Refresh the UI → all assets show "Never materialized".

To wipe just some assets instead of all:
```bash
dagster asset wipe raw_commerce/orders olin_silver_dev_jun/stg_orders
```

## Option B — full reset (materializations AND run history)
Nuke the whole local instance for a blank slate:
```bash
pkill -f "dagster dev" || true     # stop the dev server (it locks the SQLite db)
rm -rf .tmp_dagster_home_*         # delete all history
dagster dev                        # recreates an empty instance
```
(There is a `reset_dagster.sh` helper in the project dir that does this; add `--bronze`
to also drop+recreate the empty BigQuery bronze dataset.)

## Option C — from the UI
Assets page → each row's `⋯` menu → **"Wipe materializations"**. Good for one or two assets;
tedious for all.

## ⚠️ Re-running after a wipe — the append trap
Wiping only resets the UI markers; the data in BigQuery stays. So:
- Re-materializing the **bronze** (`raw_commerce`) asset makes Meltano **append again** →
  bronze duplicates. Only do this if you also reset bronze (drop+recreate empty), e.g.
  `./reset_dagster.sh --bronze`.
- If the data is already loaded and you only want to rebuild staging, re-materialize the
  **`stg_*` / dbt** assets only — skip bronze.

## Orphaned / stale asset keys
If the Asset catalog shows old keys that no longer exist in `assets.py` (e.g. after renaming
streams), they linger as orphans until wiped. Use the `⋯` → "Wipe materializations" on them,
or do a full reset (Option B), which clears everything.
