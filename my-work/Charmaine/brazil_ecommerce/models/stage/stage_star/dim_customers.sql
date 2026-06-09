SELECT
    LOWER(TRIM(CAST(customer_id AS STRING))) AS id,
    --customer_unique_id,
    CAST(customer_zip_code_prefix AS INT64) AS customer_zip_code_prefix,
    LOWER(TRIM(CAST(customer_city AS STRING))) AS customer_city,
    LOWER(TRIM(CAST(customer_state AS STRING))) AS customer_state
FROM {{ source('brazil_ecommerce', 'olist_customers_dataset') }}
WHERE customer_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY customer_id DESC) = 1