-- 1:1 dedup of bronze olist_customers_raw. One row per customer_id.
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_customers_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY 1) = 1
