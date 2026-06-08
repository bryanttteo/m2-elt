# Brazil E-Commerce dbt Project

A dbt project that models the Olist Brazil e-commerce dataset from BigQuery bronze tables into
staging and star-schema gold layers.

## Prerequisites

- Python environment with dbt-bigquery installed
- GCP credentials configured (`GOOGLE_APPLICATION_CREDENTIALS` or `gcloud auth application-default login`)
- Access to the `sctp-team2-project2-elt` BigQuery project

## Setup

```bash
dbt deps       # install packages (dbt_utils, dbt_expectations)
```

## Run

```bash
# Run all models
dbt run

# Run only staging layer
dbt run --select stage

# Run only a specific model and its upstream dependencies
dbt run --select +dim_products
```

## Test

```bash
# Test all models
dbt test

# Test only staging layer
dbt test --select stage
```

## Run + Test together

```bash
dbt build               # runs and tests all models in dependency order
dbt build --select stage
```

## Model layers

| Folder | Dataset | Materialization | Description |
|---|---|---|---|
| `models/stage/` | `brazil_ecommerce_proj_stage` | table | Joins over bronze raw tables |
| `models/stage/stage_star/` | `brazil_ecommerce_proj_stage` | table | Dimension tables (dim_*) |

## Notes

### BigQuery type names in dbt_expectations
`dbt_expectations.expect_column_values_to_be_of_type` requires the exact BigQuery type name,
not the generic SQL alias. Use `INT64` (not `integer`) and `FLOAT64` (not `float`).

### Known test failures (uniqueness)
The following uniqueness tests fail by design — these staging tables contain duplicate `id` values
because no deduplication has been applied yet. Deduplication is handled by the corresponding
`_clean` model (e.g. `fact_orders_stage_clean` uses `dbt_utils.deduplicate`):

- `unique_fact_orders_stage_id` — 12,464 duplicates
- `unique_dim_products_id` — 20 duplicates
- `unique_dim_reviews_id` — 547 duplicates
- `unique_dim_sellers_id` — 3,079 duplicates

## Resources

- [dbt docs](https://docs.getdbt.com/docs/introduction)
- [dbt_utils](https://github.com/dbt-labs/dbt-utils)
- [dbt_expectations](https://github.com/calogica/dbt-expectations)
