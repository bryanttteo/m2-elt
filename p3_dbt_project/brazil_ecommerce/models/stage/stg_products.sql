-- 1:1 dedup of bronze olist_products_raw. One row per product_id.
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_products_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY 1) = 1
