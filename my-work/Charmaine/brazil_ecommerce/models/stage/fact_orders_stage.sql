WITH source_a AS (
    SELECT 
        -- Clean strings first for proper joins
        TRIM(CAST(order_id AS STRING)) AS order_id,
        TRIM(CAST(customer_id AS STRING)) AS customer_id,
        TRIM(CAST(order_status AS STRING)) AS order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date
    FROM {{ source('brazil_ecommerce', 'olist_orders_dataset') }}
    WHERE order_id IS NOT NULL           -- PK: Required for joins
        AND customer_id IS NOT NULL      -- FK: Required for customer analysis
),

source_b AS (
    SELECT 
        TRIM(CAST(order_id AS STRING)) AS order_id,
        CAST(order_item_id AS INT64) AS order_item_id,
        TRIM(CAST(product_id AS STRING)) AS product_id,
        TRIM(CAST(seller_id AS STRING)) AS seller_id,
        shipping_limit_date,
        CAST(price AS FLOAT64) AS price,
        CAST(freight_value AS FLOAT64) AS freight_value
    FROM {{ source('brazil_ecommerce', 'olist_order_items_dataset') }}
    WHERE order_id IS NOT NULL           
        AND order_item_id IS NOT NULL    
        AND seller_id IS NOT NULL
        AND product_id IS NOT NULL
),

source_c AS (
    SELECT 
        TRIM(CAST(order_id AS STRING)) AS order_id,
        CAST(payment_sequential AS INT64) AS payment_sequential,
        TRIM(CAST(payment_type AS STRING)) AS payment_type,
        CAST(payment_installments AS INT64) AS payment_installments,
        CAST(payment_value AS FLOAT64) AS payment_value
    FROM {{ source('brazil_ecommerce', 'olist_order_payments_dataset') }}
    WHERE order_id IS NOT NULL
),

joined_table AS (
    SELECT
        -- IDs (already cleaned)
        orders.order_id AS id,
        orders.customer_id,
        
        -- Order status with COALESCE - provide default before case standardization
        LOWER(COALESCE(orders.order_status, 'unavailable')) AS order_status,
        
        -- Timestamps with explicit UTC conversion
        TIMESTAMP(CAST(orders.order_purchase_timestamp AS STRING), 'UTC') AS order_purchase_timestamp,
        TIMESTAMP(CAST(orders.order_approved_at AS STRING), 'UTC') AS order_approved_at,
        TIMESTAMP(CAST(orders.order_delivered_carrier_date AS STRING), 'UTC') AS order_delivered_carrier_date,
        TIMESTAMP(CAST(orders.order_delivered_customer_date AS STRING), 'UTC') AS order_delivered_customer_date,
        TIMESTAMP(CAST(orders.order_estimated_delivery_date AS STRING), 'UTC') AS order_estimated_delivery_date,
        
        -- From source_b
        b.order_item_id,
        b.product_id,
        b.seller_id,
        TIMESTAMP(CAST(b.shipping_limit_date AS STRING), 'UTC') AS shipping_limit_date,
        b.price,
        b.freight_value,
        
        -- From source_c with COALESCE for payment_type
        c.payment_sequential,
        LOWER(COALESCE(c.payment_type, 'not_defined')) AS payment_type,
        c.payment_installments,
        c.payment_value
        
    FROM source_a orders
    INNER JOIN source_b b ON orders.order_id = b.order_id
    LEFT JOIN source_c c ON orders.order_id = c.order_id
    -- Deduplicate: Keep one row per order-item, with the first payment method
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY orders.order_id, b.order_item_id 
        ORDER BY c.payment_sequential
    ) = 1
),

-- Validate numeric ranges (no need to handle NULLs for status/type anymore)
validated_data AS (
    SELECT
        id,
        customer_id,
        order_status,  -- Already has default value, never NULL
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        
        -- PK/FK columns - already NOT NULL
        order_item_id,
        product_id,
        seller_id,
        
        shipping_limit_date,
        
        -- Float validation (allow NULLs)
        CASE 
            WHEN price <= 0 THEN NULL 
            ELSE price 
        END AS price,
        
        CASE 
            WHEN freight_value < 0 THEN NULL 
            ELSE freight_value 
        END AS freight_value,
        
        -- Payment validation
        payment_sequential,
        payment_type,  -- Already has default value, never NULL
        payment_installments,
        payment_value
        
    FROM joined_table
),

-- Add data quality flags
quality_checks AS (
    SELECT
        *,
        -- Flag invalid delivery date (delivered before purchased)
        CASE 
            WHEN order_delivered_customer_date IS NOT NULL 
                 AND order_purchase_timestamp IS NOT NULL
                 AND order_delivered_customer_date < order_purchase_timestamp 
            THEN TRUE 
            ELSE FALSE 
        END AS has_invalid_delivery_date,
        
        -- Flag overdue deliveries (estimated delivery passed but not delivered)
        CASE 
            WHEN order_estimated_delivery_date IS NOT NULL 
                 AND CURRENT_TIMESTAMP() > order_estimated_delivery_date
                 AND order_delivered_customer_date IS NULL
            THEN TRUE 
            ELSE FALSE 
        END AS is_overdue_delivery,
        
        -- Flag high value products (over R$10,000)
        CASE 
            WHEN price > 10000 THEN TRUE 
            ELSE FALSE 
        END AS is_high_value_product,
        
        -- Flag missing delivery dates
        CASE 
            WHEN order_delivered_customer_date IS NULL 
                 AND order_status = 'delivered'
            THEN TRUE 
            ELSE FALSE 
        END AS has_missing_delivery_date,
        
        -- Flag long delivery times (over 30 days)
        CASE 
            WHEN order_delivered_customer_date IS NOT NULL 
                 AND order_purchase_timestamp IS NOT NULL
                 AND DATE_DIFF(order_delivered_customer_date, order_purchase_timestamp, DAY) > 30
            THEN TRUE 
            ELSE FALSE 
        END AS is_long_delivery,
        
        -- Flag orders without payment info
        CASE 
            WHEN payment_type = 'not_defined' OR payment_value IS NULL
            THEN TRUE 
            ELSE FALSE 
        END AS has_missing_payment_info
        
    FROM validated_data
)

-- Final SELECT
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
    -- Quality flags
    has_invalid_delivery_date,
    is_overdue_delivery,
    is_high_value_product,
    has_missing_delivery_date,
    is_long_delivery,
    has_missing_payment_info
FROM quality_checks
ORDER BY order_purchase_timestamp DESC