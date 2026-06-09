WITH cleaned_data AS (
    SELECT
        LOWER(TRIM(CAST(seller_id AS STRING))) AS id,
        CAST(seller_zip_code_prefix AS INT64) AS seller_zip_code_prefix,
        LOWER(TRIM(CAST(seller_city AS STRING))) AS seller_city,
        LOWER(TRIM(CAST(seller_state AS STRING))) AS seller_state,
        CAST(geolocation_lat AS FLOAT64) AS geolocation_lat,
        CAST(geolocation_lng AS FLOAT64) AS geolocation_lng,
        LOWER(TRIM(CAST(geolocation_city AS STRING))) AS geolocation_city,
        LOWER(TRIM(CAST(geolocation_state AS STRING))) AS geolocation_state,
        geolocation.geolocation_zip_code_prefix AS geolocation_zip_code_prefix,
        
        -- Create reusable condition for zip code match
        (seller_zip_code_prefix = geolocation_zip_code_prefix) AS zip_codes_match
        
    FROM {{ source('brazil_ecommerce', 'olist_sellers_dataset') }} sellers
    LEFT JOIN {{ source('brazil_ecommerce', 'olist_geolocation_dataset') }} geolocation 
        ON sellers.seller_zip_code_prefix = geolocation.geolocation_zip_code_prefix
    WHERE seller_id IS NOT NULL 
    QUALIFY ROW_NUMBER() OVER (PARTITION BY seller_id ORDER BY seller_id DESC) = 1
)

SELECT
    id,
    seller_zip_code_prefix,
--    geolocation_zip_code_prefix,
    zip_codes_match,
    
    -- Clean CASE statements using the reusable condition
    CASE WHEN zip_codes_match THEN geolocation_city ELSE seller_city END AS seller_city,
    CASE WHEN zip_codes_match THEN geolocation_state ELSE seller_state END AS seller_state,
    
    -- Flag is simply the opposite of zip_codes_match
--    NOT zip_codes_match AS no_address_match,
    
    -- Reference fields
--    geolocation_city AS geolocation_city_reference,
--    geolocation_state AS geolocation_state_reference,
--    geolocation_lat,
--    geolocation_lng
    
FROM cleaned_data
