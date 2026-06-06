# macros / cross_db — dialect quarantine  (MIGRATION SEAM)
**Module 3** · Owner: Hoong Jun

## Purpose
Isolate every engine-specific SQL function in ONE place using dbt's `adapter.dispatch`. This is what makes the future BigQuery → Trino (on-prem) migration a ~5-macro rewrite instead of touching 50 models.

## Needs
- The `name:` in `dbt_project.yml` must equal the dispatch namespace (`sctp_team2`).

## Produces
- Cross-database macros, each with a `bigquery__` and a `trino__` implementation.

## Rule for the whole team
Never write `DATE_DIFF`, `DATE_ADD`, `QUALIFY`, array, or other dialect-specific functions inline in a model. Route through a macro here.

## Files
- `day_diff.sql` — date difference in days (bigquery + trino variants).
- `surrogate_key.sql` — deterministic surrogate key generation.
