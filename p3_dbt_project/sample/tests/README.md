# tests — dbt singular & custom tests  (supports Module 4)
**Owner:** Charmaine / Jenn Fang (M4) · with Hoong Jun (M3)

## Purpose
Singular (one-off SQL) and custom generic tests that go beyond dbt's built-in `unique`/`not_null`/`relationships`/`accepted_values`. Generic column tests live in the model YAML (`models/gold/_gold.yml`); this folder is for bespoke assertions.

## Needs
- Built silver/gold models.

## Produces
- Reusable/singular tests that run as part of `dbt build` and `dbt test`.

## Examples to implement
- **Reconciliation:** total gmv in `mart_monthly_revenue` equals SUM(total_line_value) in `fct_order_items` for the same period.
- **Business logic:** delivery_lead_time_days is non-negative for delivered orders.
- **RFM integrity:** every customer has exactly one rfm_segment.

## Run
```bash
dbt test                       # runs YAML + singular tests
dbt build --select gold        # build + test the gold layer
```
