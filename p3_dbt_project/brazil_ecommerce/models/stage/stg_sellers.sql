-- 1:1 dedup of bronze olist_sellers_raw. One row per seller_id.
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_sellers_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY seller_id ORDER BY 1) = 1
