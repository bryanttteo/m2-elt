-- 1:1 dedup of bronze olist_order_items_raw. PK = (order_id, order_item_id).
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_order_items_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id, order_item_id ORDER BY 1) = 1
