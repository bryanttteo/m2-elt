-- 1:1 dedup of bronze olist_orders_raw. One row per order_id (latest purchase).
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_orders_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_purchase_timestamp DESC) = 1
