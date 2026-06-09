-- Order fact at ORDER-ITEM grain. Composite PK = (id, order_item_id), one row per
-- order line item. Ported from Charmaine's fact_orders_stage: order_status defaulting,
-- price/freight validation, and data-quality flag columns. Built on the stg_* layer.
-- FKs: customer_id -> dim_customers, product_id -> dim_products, seller_id -> dim_sellers.
WITH orders AS (
    SELECT
        TRIM(CAST(order_id AS STRING))     AS order_id,
        TRIM(CAST(customer_id AS STRING))  AS customer_id,
        order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date
    FROM {{ ref('stg_orders') }}
    WHERE order_id IS NOT NULL
      AND customer_id IS NOT NULL
),

items AS (
    SELECT
        TRIM(CAST(order_id AS STRING))   AS order_id,
        CAST(order_item_id AS INT64)     AS order_item_id,
        TRIM(CAST(product_id AS STRING)) AS product_id,
        TRIM(CAST(seller_id AS STRING))  AS seller_id,
        shipping_limit_date,
        CAST(price AS FLOAT64)           AS price,
        CAST(freight_value AS FLOAT64)   AS freight_value
    FROM {{ ref('stg_order_items') }}
    WHERE order_id IS NOT NULL
      AND order_item_id IS NOT NULL
      AND seller_id IS NOT NULL
      AND product_id IS NOT NULL
),

payments AS (
    SELECT
        TRIM(CAST(order_id AS STRING))   AS order_id,
        CAST(payment_sequential AS INT64) AS payment_sequential,
        payment_type,
        CAST(payment_installments AS INT64) AS payment_installments,
        CAST(payment_value AS FLOAT64)   AS payment_value
    FROM {{ ref('stg_order_payments') }}
    WHERE order_id IS NOT NULL
),

joined AS (
    SELECT
        o.order_id AS id,
        o.customer_id,
        -- Default missing status to 'unavailable' before standardising case.
        LOWER(COALESCE(o.order_status, 'unavailable')) AS order_status,
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
        -- Replace null payment_type with the accepted 'not_defined' value.
        LOWER(COALESCE(p.payment_type, 'not_defined')) AS payment_type,
        p.payment_installments,
        p.payment_value,
        -- Deterministic dedup to one row per order line item.
        ROW_NUMBER() OVER (
            PARTITION BY o.order_id, COALESCE(i.order_item_id, 0)
            ORDER BY o.customer_id
        ) AS row_num
    FROM orders o
    LEFT JOIN items i    ON o.order_id = i.order_id
    LEFT JOIN payments p ON o.order_id = p.order_id
),

deduped AS (
    SELECT * EXCEPT (row_num)
    FROM joined
    WHERE row_num = 1
),

validated AS (
    SELECT
        * EXCEPT (price, freight_value),
        -- Null-out implausible monetary values rather than dropping the row.
        CASE WHEN price <= 0 THEN NULL ELSE price END                 AS price,
        CASE WHEN freight_value < 0 THEN NULL ELSE freight_value END   AS freight_value
    FROM deduped
)

SELECT
    id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value,
    payment_sequential,
    payment_type,
    payment_installments,
    payment_value,
    -- Data-quality flags ---------------------------------------------------
    -- Delivered before it was purchased.
    CASE
        WHEN order_delivered_customer_date IS NOT NULL
             AND order_purchase_timestamp IS NOT NULL
             AND order_delivered_customer_date < order_purchase_timestamp
        THEN TRUE ELSE FALSE
    END AS has_invalid_delivery_date,
    -- Estimated delivery passed but order never delivered.
    CASE
        WHEN order_estimated_delivery_date IS NOT NULL
             AND CURRENT_TIMESTAMP() > order_estimated_delivery_date
             AND order_delivered_customer_date IS NULL
        THEN TRUE ELSE FALSE
    END AS is_overdue_delivery,
    -- Item priced over R$10,000.
    CASE WHEN price > 10000 THEN TRUE ELSE FALSE END AS is_high_value_product,
    -- Marked delivered but no delivery date recorded.
    CASE
        WHEN order_delivered_customer_date IS NULL
             AND order_status = 'delivered'
        THEN TRUE ELSE FALSE
    END AS has_missing_delivery_date,
    -- Delivery took more than 30 days.
    CASE
        WHEN order_delivered_customer_date IS NOT NULL
             AND order_purchase_timestamp IS NOT NULL
             AND DATE_DIFF(order_delivered_customer_date, order_purchase_timestamp, DAY) > 30
        THEN TRUE ELSE FALSE
    END AS is_long_delivery,
    -- No usable payment information.
    CASE
        WHEN payment_type = 'not_defined' OR payment_value IS NULL
        THEN TRUE ELSE FALSE
    END AS has_missing_payment_info,
    -- Order with no matching line item.
    CASE WHEN order_item_id IS NULL THEN TRUE ELSE FALSE END AS has_no_items
FROM validated
WHERE customer_id IS NOT NULL
ORDER BY order_purchase_timestamp DESC, id
