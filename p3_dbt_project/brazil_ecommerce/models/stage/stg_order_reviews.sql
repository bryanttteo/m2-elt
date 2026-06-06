-- 1:1 dedup of bronze olist_order_reviews_raw. One row per review_id (latest answer).
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_order_reviews_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY review_answer_timestamp DESC) = 1
