SELECT
    customer_id AS id,
    --customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM {{ source('brazil_ecommerce', 'olist_customers_raw') }}
