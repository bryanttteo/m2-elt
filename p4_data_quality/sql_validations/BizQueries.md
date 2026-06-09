# From Sales, Marketing perspective:

## 1. Revenue Performance
### Monthly revenue trend with order volume
SELECT
    DATE_TRUNC(order_purchase_timestamp, MONTH) AS month,
    COUNT(DISTINCT id) AS total_orders,
    COUNT(DISTINCT customer_id) AS unique_customers,
    ROUND(SUM(price), 2) AS gross_revenue,
    ROUND(SUM(freight_value), 2) AS total_freight,
    ROUND(SUM(price + freight_value), 2) AS total_revenue,
    ROUND(AVG(price), 2) AS avg_order_value
FROM fact_orders_stage
WHERE order_status = 'delivered'
    AND order_purchase_timestamp IS NOT NULL
GROUP BY 1
ORDER BY 1

## 2. Seller Performance Ranking
### Top sellers by revenue with delivery quality
SELECT
    s.id AS seller_id,
    s.seller_state,
    s.seller_city,
    COUNT(DISTINCT f.id) AS total_orders,
    ROUND(SUM(f.price), 2) AS total_revenue,
    ROUND(AVG(f.price), 2) AS avg_order_value,
    ROUND(AVG(r.review_score), 2) AS avg_review_score,
    COUNTIF(f.is_long_delivery) AS long_delivery_count,
    COUNTIF(f.has_invalid_delivery_date) AS invalid_delivery_count
FROM fact_orders_stage f
LEFT JOIN dim_sellers s ON f.seller_id = s.id
LEFT JOIN dim_reviews r ON f.id = r.order_id
WHERE f.order_status = 'delivered'
GROUP BY 1, 2, 3
ORDER BY total_revenue DESC

## 3. Product Category Performance
### Revenue and review score by Product Category
SELECT
    p.product_category,
    COUNT(DISTINCT f.id) AS total_orders,
    ROUND(SUM(f.price), 2) AS total_revenue,
    ROUND(AVG(f.price), 2) AS avg_price,
    ROUND(AVG(f.freight_value), 2) AS avg_freight,
    ROUND(AVG(r.review_score), 2) AS avg_review_score,
    COUNTIF(f.is_long_delivery) AS long_deliveries,
    -- Freight as % of price (logistics efficiency)
    ROUND(AVG(f.freight_value / NULLIF(f.price, 0)) * 100, 2) AS freight_pct_of_price
FROM fact_orders_stage f
LEFT JOIN dim_products p ON f.product_id = p.id
LEFT JOIN dim_reviews r ON f.id = r.order_id
WHERE f.order_status = 'delivered'
GROUP BY 1
ORDER BY total_revenue DESC

## 4. Payment Method Analysis
### Payment behaviour by type and installments
SELECT
    payment_type,
    payment_installments,
    COUNT(DISTINCT id) AS total_orders,
    ROUND(SUM(price), 2) AS total_revenue,
    ROUND(AVG(price), 2) AS avg_order_value,
    -- High value orders tend to use more installments
    ROUND(AVG(payment_value), 2) AS avg_payment_value
FROM fact_orders_stage
WHERE order_status = 'delivered'
    AND payment_type != 'not_defined'
GROUP BY 1, 2
ORDER BY 1, 2

## 5. Delivery Performance
### SLA analysis by seller state
SELECT
    s.seller_state,
    COUNT(DISTINCT f.id) AS total_orders,
    ROUND(AVG(
        DATE_DIFF(f.order_delivered_customer_date, f.order_purchase_timestamp, DAY)
    ), 1) AS avg_delivery_days,
    ROUND(AVG(
        DATE_DIFF(f.order_estimated_delivery_date, f.order_delivered_customer_date, DAY)
    ), 1) AS avg_days_vs_estimate, -- positive = early, negative = late
    COUNTIF(f.is_long_delivery) AS long_deliveries,
    COUNTIF(f.is_overdue_delivery) AS overdue_deliveries,
    ROUND(COUNTIF(f.is_overdue_delivery) / COUNT(*) * 100, 2) AS overdue_rate_pct
FROM fact_orders_stage f
LEFT JOIN dim_sellers s ON f.seller_id = s.id
WHERE f.order_status = 'delivered'
    AND f.order_delivered_customer_date IS NOT NULL
GROUP BY 1
ORDER BY avg_delivery_days DESC

## 6. Customer Segmentation
### Recency, Frequency, Monetary segmentation
WITH rfm AS (
    SELECT
        customer_id,
        DATE_DIFF(CURRENT_DATE(), MAX(DATE(order_purchase_timestamp)), DAY) AS recency_days,
        COUNT(DISTINCT id) AS frequency,
        ROUND(SUM(price), 2) AS monetary
    FROM fact_orders_stage
    WHERE order_status = 'delivered'
    GROUP BY 1
)
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    CASE
        WHEN recency_days <= 90 AND frequency >= 3 AND monetary >= 500 THEN 'Champion'
        WHEN recency_days <= 180 AND frequency >= 2 THEN 'Loyal'
        WHEN recency_days <= 90 THEN 'Recent'
        WHEN recency_days > 365 THEN 'Churned'
        ELSE 'At Risk'
    END AS customer_segment
FROM rfm
ORDER BY monetary DESC

## 7. Geographic revenue heatmap
### Revenue by customer state for campaign targeting
SELECT
    c.customer_state,
    COUNT(DISTINCT f.customer_id) AS unique_customers,
    COUNT(DISTINCT f.id) AS total_orders,
    ROUND(SUM(f.price), 2) AS total_revenue,
    ROUND(AVG(f.price), 2) AS avg_order_value,
    ROUND(AVG(r.review_score), 2) AS avg_satisfaction,
    -- Orders per customer (engagement rate)
    ROUND(COUNT(DISTINCT f.id) / COUNT(DISTINCT f.customer_id), 2) AS orders_per_customer
FROM fact_orders_stage f
LEFT JOIN dim_customers c ON f.customer_id = c.id
LEFT JOIN dim_reviews r ON f.id = r.order_id
WHERE f.order_status = 'delivered'
GROUP BY 1
ORDER BY total_revenue DESC

## 8. Review Sentiment vs Sales Impact
### Does review score correlate with repeat category purchases?
SELECT
    p.product_category,
    r.review_score,
    COUNT(DISTINCT f.id) AS total_orders,
    ROUND(AVG(f.price), 2) AS avg_price,
    ROUND(AVG(
        DATE_DIFF(f.order_delivered_customer_date, f.order_purchase_timestamp, DAY)
    ), 1) AS avg_delivery_days,
    -- Low scores with long delivery = actionable insight
    ROUND(AVG(f.freight_value), 2) AS avg_freight
FROM fact_orders_stage f
LEFT JOIN dim_products p ON f.product_id = p.id
LEFT JOIN dim_reviews r ON f.id = r.order_id
WHERE r.review_score IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2

