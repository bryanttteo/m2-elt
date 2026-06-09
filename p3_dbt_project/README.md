# dbt Project — ELT / Transformation  (Module 3)
**Owner:** Hoong Jun · **Developer:** Charmaine Wong SM · **Support:** Bryan Teo · **Role:** Analytics Engineering

## Purpose
Transform bronze (`raw_commerce`) into the **silver** and **gold** medallion layers, implementing M2's star-schema design as governed, tested, versioned dbt models. Gold marts are materialized as **BigQuery Iceberg** tables (the lakehouse differentiator).

## Needs (inputs)
- Bronze tables in `raw_commerce` (from M1).
- The star-schema design from M2 (`p2_warehouse_design/star_schema.md`) — the spec these models implement.
- GCP auth + `silver_commerce` and `gold_commerce` datasets + the BigLake connection (for Iceberg).

## Produces (outputs)
- **`silver_commerce.*`** — cleaned, typed, conformed models (`models/silver/`).
- **`gold_commerce.*`** — dims, facts, consumer marts as Iceberg tables (`models/gold/`).
- dbt docs + lineage (`dbt docs generate`).

## Hand-off to next (→ M4, M5)
- M4 attaches tests/contracts to the gold models (`models/gold/_gold.yml`).
- M5 queries the gold marts (`gold_commerce.mart_*`) for analysis.

## Layout
- `models/silver/` — silver = staging + intermediate combined (clean/type/conform).
- `models/gold/` — marts (dim_, fct_, mart_), materialized as Iceberg.
- `macros/cross_db/` — **migration seam**: dialect-specific SQL quarantined here.
- `profiles.yml` — dual target: `bq` (active) + `trino` (stubbed for on-prem).
- `catalogs.yml` — BigLake/Iceberg catalog config.

## Conventions
- **dbt owns every write** to silver/gold.
- Never write engine-specific SQL inline — route through a `cross_db` macro.
- `name:` and `profile:` in `dbt_project.yml` must both be `sctp_team2` (matches dispatch namespace + profiles key).

## Run
```bash
dbt deps
dbt build      # runs + tests silver and gold
dbt docs generate && dbt docs serve
```
