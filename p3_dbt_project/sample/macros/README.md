# macros — reusable SQL
**Module 3** · Owner: Hoong Jun

## Purpose
Reusable Jinja/SQL macros shared across models. Keeps logic DRY and keeps the codebase portable across engines.

## Structure
- **`cross_db/`** — **migration seam**: every engine-specific SQL function (date math, surrogate keys, etc.) is quarantined here with `bigquery__` and `trino__` variants via `adapter.dispatch`. This is what makes the BigQuery → on-prem Trino migration cheap.

## Rule
Any SQL that differs between BigQuery and Trino must live in `cross_db/`, never inline in a model.
