-- 1:1 dedup of bronze olist_geolocation_raw to ONE row per zip prefix.
-- Bronze holds many lat/lng points per zip; collapsing to one keeps the
-- seller/customer zip joins downstream from fanning out.
SELECT *
FROM {{ source('brazil_ecommerce', 'olist_geolocation_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY geolocation_zip_code_prefix ORDER BY 1) = 1
