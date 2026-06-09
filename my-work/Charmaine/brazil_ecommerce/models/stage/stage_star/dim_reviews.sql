SELECT 
    --review_id,
    LOWER(TRIM(CAST(order_id AS STRING))) AS id,
    CAST(review_score AS INT64) AS review_score,
    LOWER(TRIM(CAST(review_comment_title AS STRING))) AS review_comment_title,
    LOWER(TRIM(CAST(review_comment_message AS STRING))) AS review_comment_message,
    CAST(review_creation_date AS TIMESTAMP) AS review_creation_date,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
FROM {{ source('brazil_ecommerce', 'olist_order_reviews_dataset') }}
WHERE order_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) = 1