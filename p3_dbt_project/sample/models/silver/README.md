# models / silver — cleaned & conformed  (SILVER tier)
**Module 3** · Owner: Hoong Jun / Bryan

## Purpose
Turn raw bronze into clean, typed, conformed models. Silver = **staging + intermediate combined** (no separate staging folder, per project convention).

## Needs
- Bronze sources registered in `_sources.yml` (points at `raw_commerce`).

## Produces
- `silver_commerce.*` models (materialized as views): renamed columns, explicit casts, deduped, null-filtered, light joins/business prep.

## Hand-off
Gold models (`../gold/`) `ref()` these silver models — never the raw sources directly.

## Files
- `_sources.yml` — declares bronze (`raw_commerce`) tables as dbt sources.
- `silver_<entity>.sql` — one per source entity (orders, order_items, customers, products, payments, reviews).

## Rules
- Cast types explicitly; no implicit casts.
- No engine-specific functions inline → use `macros/cross_db/`.
