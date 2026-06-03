WITH source_a AS (
    SELECT * FROM {{ source('brazil_ecommerce', 'olist_orders_dataset') }}
),
source_b AS (
    SELECT * FROM {{ source('brazil_ecommerce', 'olist_order_items_dataset') }}
),
source_c AS (
    SELECT * FROM {{ source('brazil_ecommerce', 'olist_order_payments_dataset') }}
)
SELECT
    orders.order_id AS id,
    orders.customer_id,
    orders.order_status,
    CAST(orders.order_purchase_timestamp AS TIMESTAMP) AS order_purchase_timestamp,
    CAST(orders.order_approved_at AS TIMESTAMP) AS order_approved_at,
    CAST(orders.order_delivered_carrier_date AS TIMESTAMP) AS order_delivered_carrier_date,
    CAST(orders.order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    CAST(orders.order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date,
    b.order_item_id,
    --b.product_id,
    b.seller_id,
    CAST(b.shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
    b.price,
    b.freight_value,
    c.payment_sequential,
    c.payment_type,
    c.payment_installments,
    c.payment_value
FROM source_a orders
LEFT JOIN source_b b ON orders.order_id = b.order_id
LEFT JOIN source_c c ON orders.order_id = c.order_id
WHERE orders.order_id IS NOT NULL AND 
orders.customer_id IS NOT NULL AND 
b.order_item_id IS NOT NULL AND 
b.seller_id IS NOT NULL