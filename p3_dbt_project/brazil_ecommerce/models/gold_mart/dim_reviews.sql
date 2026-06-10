-- Review dimension as a Type-2 SCD, sourced from the dbt-managed snapshot
-- (reviews_dbt_scd_snapshot) to simulate slowly-changing history. One row per review
-- *version*: PK = id (dbt_scd_id, a surrogate per version). review_id / order_id are
-- business keys here and are NOT unique (history is preserved). is_current flags the
-- live version (dbt_valid_to IS NULL).
SELECT
    dbt_scd_id AS id,
    review_id,
    order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp,
    dbt_valid_from AS valid_from,
    dbt_valid_to   AS valid_to,
    (dbt_valid_to IS NULL) AS is_current
FROM {{ ref('reviews_dbt_scd_snapshot') }}
WHERE order_id IS NOT NULL
