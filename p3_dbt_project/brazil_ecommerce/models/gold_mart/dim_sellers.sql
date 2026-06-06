-- Seller dimension enriched with one lat/lng per zip. PK = id (seller_id).
-- stg_geolocation is already one row per zip, so this join does not fan out.
SELECT
    s.seller_id AS id,
    s.seller_zip_code_prefix,
    s.seller_city,
    s.seller_state,
    g.geolocation_lat,
    g.geolocation_lng,
    g.geolocation_city,
    g.geolocation_state
FROM {{ ref('stg_sellers') }} s
LEFT JOIN {{ ref('stg_geolocation') }} g
    ON s.seller_zip_code_prefix = g.geolocation_zip_code_prefix
