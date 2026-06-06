# models / gold — marts  (GOLD tier)
**Module 3** · Owner: Hoong Jun / Bryan

## Purpose
The star schema and consumer marts that M5 and BI consume. Materialized as **BigQuery Iceberg** tables (open lakehouse).

## Needs
- Silver models (`../silver/`) as the only upstream — gold `ref()`s silver, not raw.
- The BigLake catalog config (`catalogs.yml`) for Iceberg materialization.

## Produces
- `gold_commerce.dim_customer / dim_product / dim_date / fct_order_items`
- `gold_commerce.mart_customer_360` (RFM, lifetime value)
- `gold_commerce.mart_monthly_revenue` (gmv by month × category)
- Iceberg/Parquet files in `gs://sctp-team2-project2-data/warehouse/`.

## Hand-off
- M4 attaches contracts + tests here via `_gold.yml`.
- M5 queries `gold_commerce.mart_*` only.

## Files
- `_gold.yml` — model docs, **contracts**, and M4 tests.
- `dim_*.sql`, `fct_*.sql`, `mart_*.sql`.

## Config (every gold model)
```sql
{{ config(materialized='table', table_format='iceberg', catalog='biglake_catalog') }}
```
