-- Order fact. PK = id (order_id), one row per order.
-- Combines the former fact_orders_stage join + fact_orders_stage_clean dedup, plus
-- the null-id filters added in commits 1658304 / c61bea9. FKs: customer_id ->
-- dim_customers, product_id -> dim_products, seller_id -> dim_sellers.
WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),
items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),
payments AS (
    SELECT * FROM {{ ref('stg_order_payments') }}
)
SELECT
    o.order_id AS id,
    o.customer_id,
    o.order_status,
    CAST(o.order_purchase_timestamp AS TIMESTAMP)      AS order_purchase_timestamp,
    CAST(o.order_approved_at AS TIMESTAMP)             AS order_approved_at,
    CAST(o.order_delivered_carrier_date AS TIMESTAMP)  AS order_delivered_carrier_date,
    CAST(o.order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    CAST(o.order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    CAST(i.shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
    i.price,
    i.freight_value,
    p.payment_sequential,
    -- Replace null payment_type with 'not_defined' (an accepted value).
    COALESCE(p.payment_type, 'not_defined') AS payment_type,
    p.payment_installments,
    p.payment_value
FROM orders o
LEFT JOIN items i    ON o.order_id = i.order_id
LEFT JOIN payments p ON o.order_id = p.order_id
WHERE o.order_id IS NOT NULL
  AND o.customer_id IS NOT NULL
  AND i.order_item_id IS NOT NULL
  AND i.seller_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY o.order_id ORDER BY o.order_purchase_timestamp DESC) = 1
