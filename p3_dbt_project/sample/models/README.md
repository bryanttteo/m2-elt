# models — dbt transformation layers
**Module 3** · Owner: Hoong Jun / Bryan

## Purpose
Holds the dbt models, organized by **medallion tier**. dbt owns the silver and gold tiers (bronze is the raw dataset produced upstream by EL).

## Structure
- **`silver/`** — cleaned, typed, conformed models (= staging + intermediate combined). Materialized as views in `silver_commerce`.
- **`gold/`** — marts: dims, facts, consumer marts. Materialized as **Iceberg tables** in `gold_commerce`.

## Flow
```
raw_commerce (bronze)  →  models/silver/*  →  models/gold/*  →  consumers (M5/BI)
```

## Rule
Models only ever read from the tier directly below: silver reads bronze sources; gold `ref()`s silver. Never skip a tier.
