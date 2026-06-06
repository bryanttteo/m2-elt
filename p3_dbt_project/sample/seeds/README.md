# seeds — static reference data
**Module 3** · Owner: Hoong Jun / Bryan

## Purpose
Small static CSVs versioned in the repo and loaded by dbt as tables (`dbt seed`). For reference/lookup data that isn't part of the raw source feed.

## Needs
- CSV files placed in this folder.

## Produces
- BigQuery tables from each seed CSV, usable via `{{ ref('<seed_name>') }}`.

## Likely uses here
- A generated **date dimension** seed (if not built in SQL) for `dim_date`.
- Manual category groupings / segment label mappings if needed.

## Note
Keep seeds SMALL (reference data only). Bulk data belongs in bronze via EL, not seeds.

## Run
```bash
dbt seed
```
