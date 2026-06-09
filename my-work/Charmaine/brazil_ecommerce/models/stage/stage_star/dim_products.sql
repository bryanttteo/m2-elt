SELECT
    LOWER(TRIM(CAST(product_id AS STRING))) AS id,
--    CAST(items.order_item_id AS INT64) AS id,
    LOWER(TRIM(CAST(category.string_field_1 AS STRING))) AS product_category,
    CAST(product_name_lenght AS INT64) AS product_name_length,
    CAST(product_description_lenght AS INT64) AS product_description_length,
    CAST(product_photos_qty AS INT64) AS product_photos_qty,
    CAST(product_weight_g AS INT64) AS product_weight_g,
    CAST(product_length_cm AS INT64) AS product_length_cm,
    CAST(product_height_cm AS INT64) AS product_height_cm,
    CAST(product_width_cm AS INT64) AS product_width_cm
FROM {{ source('brazil_ecommerce', 'olist_products_dataset') }} products
LEFT JOIN {{ source('brazil_ecommerce', 'product_category_name_translation') }} AS category
    ON products.product_category_name = category.string_field_0
--LEFT JOIN {{ source('brazil_ecommerce', 'olist_order_items_dataset') }} AS items 
--    ON products.product_id = items.product_id
WHERE
    product_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY product_id DESC) = 1