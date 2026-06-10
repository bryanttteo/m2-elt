-- Geolocation dimension as a Type-2 SCD, sourced from the dbt-managed snapshot
-- (geolocation_dbt_scd_snapshot) to simulate slowly-changing history. One row per
-- zip-prefix *version*: PK = id (dbt_scd_id, a surrogate per version).
-- geolocation_zip_code_prefix is the business key and is NOT unique (history is
-- preserved). is_current flags the live version (dbt_valid_to IS NULL).
SELECT
    dbt_scd_id AS id,
    geolocation_zip_code_prefix,
    geolocation_lat,
    geolocation_lng,
    geolocation_city,
    geolocation_state,
    dbt_valid_from AS valid_from,
    dbt_valid_to   AS valid_to,
    (dbt_valid_to IS NULL) AS is_current
FROM {{ ref('geolocation_dbt_scd_snapshot') }}
