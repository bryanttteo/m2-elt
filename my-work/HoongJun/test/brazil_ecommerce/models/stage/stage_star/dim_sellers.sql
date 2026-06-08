SELECT
    seller_id AS id,
    seller_zip_code_prefix,
    seller_city,
    seller_state,
    geolocation_lat,
    geolocation_lng,
    geolocation_city,
    geolocation_state
FROM {{ source('brazil_ecommerce', 'olist_sellers_raw') }} sellers
LEFT JOIN {{ source('brazil_ecommerce', 'olist_geolocation_raw') }} geolocation ON sellers.seller_zip_code_prefix = geolocation.geolocation_zip_code_prefix
WHERE seller_id IS NOT NULL