SELECT 
    --review_id,
    order_id as id,
    --id,
    review_score,
    review_comment_title,
    review_comment_message,
    --review_creation_date,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
FROM {{ source('brazil_ecommerce', 'olist_order_reviews_raw') }}
WHERE order_id IS NOT NULL