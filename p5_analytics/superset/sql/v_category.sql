-- v_category — item revenue by month / state / product category (catalog charts).
-- Mirrors p5_analytics/dash/queries.py CATEGORY_SQL. Item grain (not collapsed to order).
SELECT
  DATE(DATE_TRUNC(DATE(f.order_purchase_timestamp), MONTH)) AS order_month,
  c.customer_state,
  COALESCE(p.product_category, 'unknown')                   AS product_category,
  SUM(f.price)                                             AS gmv,
  COUNT(*)                                                 AS n_items
FROM `{{PROJECT}}.{{GOLD}}.fact_orders` f
LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_products`  p ON f.product_id  = p.id
LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_customers` c ON f.customer_id = c.id
WHERE f.order_purchase_timestamp IS NOT NULL
GROUP BY 1, 2, 3
