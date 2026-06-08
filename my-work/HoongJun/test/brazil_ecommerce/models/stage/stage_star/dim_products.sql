SELECT
    items.order_item_id AS id,
    category.product_category_name_english AS product_category,
    product_name_lenght,
    product_description_lenght,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
FROM {{ source('brazil_ecommerce', 'olist_products_raw') }} products
LEFT JOIN {{ source('brazil_ecommerce', 'product_category_name_translation_raw') }} AS category
    ON products.product_category_name = category.product_category_name
LEFT JOIN {{ source('brazil_ecommerce', 'olist_order_items_raw') }} AS items 
    ON products.product_id = items.product_id
WHERE
    items.order_item_id IS NOT NULL