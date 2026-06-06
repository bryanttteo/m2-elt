-- 1:1 dedup of bronze olist_order_payments_raw. PK = (order_id, payment_sequential).
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_order_payments_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id, payment_sequential ORDER BY 1) = 1
