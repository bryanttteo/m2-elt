-- 1:1 dedup of bronze product_category_name_translation. One row per pt category name.
SELECT *
FROM {{ source('brazil_ecommerce', 'product_category_name_translation_raw') }}
QUALIFY ROW_NUMBER() OVER (PARTITION BY product_category_name ORDER BY 1) = 1
