{% snapshot reviews_snapshot %}

{{
  config(
    target_schema='snapshots',
    unique_key='review_id',
    strategy='timestamp',
    updated_at='review_answer_timestamp'
  )
}}

WITH item AS (
    SELECT
        review_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_answer_timestamp,
        review_creation_date
    FROM {{ source('brazil_ecommerce', 'olist_order_reviews_raw') }}
),

grouped_data AS (
    SELECT DISTINCT
        review_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_answer_timestamp,
        FIRST_VALUE(review_creation_date) OVER (
            PARTITION BY review_id, review_score, review_comment_title, review_comment_message, review_answer_timestamp
            ORDER BY review_creation_date
        ) AS start_date,

        LAST_VALUE(review_creation_date) OVER (
            PARTITION BY review_id, review_score, review_comment_title, review_comment_message, review_answer_timestamp
            ORDER BY review_creation_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS end_date

    FROM item

    QUALIFY RANK() OVER (
        PARTITION BY review_id, review_score, review_comment_title, review_comment_message, review_answer_timestamp
        ORDER BY review_creation_date
    ) = 1
)

SELECT
    review_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_answer_timestamp,
    CAST(start_date AS TIMESTAMP) AS start_at,
    CAST(LEAD(start_date) OVER (PARTITION BY review_id ORDER BY start_date) AS TIMESTAMP) AS end_at,
    IF(LEAD(start_date) OVER (PARTITION BY review_id ORDER BY start_date) IS NULL, CURRENT_TIMESTAMP(), NULL) AS updated_at

FROM grouped_data

ORDER BY review_id, start_at, end_at

{% endsnapshot %}