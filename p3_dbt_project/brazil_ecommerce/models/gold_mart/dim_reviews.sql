-- Review dimension keyed by order. PK = id (order_id), one (latest) review per order.
SELECT
    order_id AS id,
    review_id,
    review_score,
    review_comment_title,
    review_comment_message,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
FROM {{ ref('stg_order_reviews') }}
WHERE order_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) = 1
