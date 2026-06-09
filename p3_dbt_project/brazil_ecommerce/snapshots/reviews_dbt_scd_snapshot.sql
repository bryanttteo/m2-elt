{% snapshot reviews_dbt_scd_snapshot %}

{#
  dbt-managed SCD Type 2 history of order reviews.

  Unlike reviews_snapshot.sql (which hand-builds its own start/end ranges), this
  snapshot returns the *current* state of each review and lets dbt manage the SCD2
  columns automatically: each run dbt detects changes via review_answer_timestamp
  (timestamp strategy) and maintains dbt_valid_from / dbt_valid_to / dbt_scd_id.

  Source is the staging model stg_order_reviews (already deduped 1:1 per review_id),
  not raw bronze.
#}

{{
  config(
    target_schema='snapshots',
    unique_key='review_id',
    strategy='timestamp',
    updated_at='review_answer_timestamp'
  )
}}

SELECT
    review_id,
    order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date,
    review_answer_timestamp
FROM {{ ref('stg_order_reviews') }}

{% endsnapshot %}
