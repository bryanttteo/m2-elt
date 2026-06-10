-- v_orders — order-grain enriched base (the workhorse virtual dataset).
-- Mirrors p5_analytics/dash/queries.py ORDERS_SQL + the pandas derivations in
-- p5_analytics/dash/metrics.py, expressed as BigQuery SQL so Superset can aggregate it.
-- One row per order. Reads the gold mart only.
WITH ord AS (
  SELECT
    id                                        AS order_id,
    ANY_VALUE(customer_id)                    AS customer_id,
    ANY_VALUE(order_status)                   AS order_status,
    ANY_VALUE(order_purchase_timestamp)       AS purchase_ts,
    ANY_VALUE(order_delivered_customer_date)  AS delivered_ts,
    ANY_VALUE(order_estimated_delivery_date)  AS estimated_ts,
    SUM(price)                                AS gmv,
    SUM(freight_value)                        AS freight,
    COUNT(*)                                  AS n_items,
    ANY_VALUE(payment_type)                   AS payment_type,
    MAX(payment_installments)                 AS payment_installments
  FROM `{{PROJECT}}.{{GOLD}}.fact_orders`
  WHERE order_purchase_timestamp IS NOT NULL
  GROUP BY id
),
joined AS (
  SELECT
    o.order_id,
    o.order_status,
    o.purchase_ts,
    DATE(DATE_TRUNC(DATE(o.purchase_ts), MONTH)) AS order_month,
    o.delivered_ts,
    o.estimated_ts,
    o.gmv,
    o.freight,
    o.n_items,
    o.payment_type,
    o.payment_installments,
    c.customer_unique_id,
    c.customer_state,
    r.review_score,
    CASE WHEN o.delivered_ts IS NOT NULL
         THEN DATE_DIFF(DATE(o.delivered_ts), DATE(o.purchase_ts), DAY) END AS delivery_days,
    CASE WHEN o.delivered_ts IS NOT NULL AND o.estimated_ts IS NOT NULL
         THEN DATE_DIFF(DATE(o.delivered_ts), DATE(o.estimated_ts), DAY) END AS days_vs_estimate
  FROM ord o
  LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_customers` c ON o.customer_id = c.id
  LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_reviews`   r ON o.order_id    = r.id
),
windowed AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id) AS order_seq,
    COUNT(*)     OVER (PARTITION BY customer_unique_id)                                AS cust_total_orders,
    MIN(order_month) OVER (PARTITION BY customer_unique_id)                            AS cohort_month
  FROM joined
)
SELECT
  order_id,
  customer_unique_id,
  customer_state,
  order_status,
  purchase_ts,
  order_month,
  cohort_month,
  delivered_ts,
  gmv,
  freight,
  n_items,
  payment_type,
  payment_installments,
  review_score,
  delivery_days,
  days_vs_estimate,
  order_seq,
  cust_total_orders,
  order_seq > 1                  AS is_repeat_order,         -- not this customer's first order
  order_seq < cust_total_orders  AS has_subsequent_order,    -- another order followed (reorder signal)
  order_status = 'delivered'     AS is_delivered,
  days_vs_estimate > 0           AS is_late,
  CASE
    WHEN days_vs_estimate IS NULL THEN NULL
    WHEN days_vs_estimate <= 0    THEN '1 · Early / on-time'
    WHEN days_vs_estimate <= 3    THEN '2 · 1-3 days late'
    WHEN days_vs_estimate <= 7    THEN '3 · 4-7 days late'
    ELSE                               '4 · 8+ days late'
  END AS delivery_bucket,
  CASE
    WHEN review_score IS NULL THEN NULL
    WHEN review_score <= 2    THEN '1-2 ★ detractor'
    WHEN review_score  = 3    THEN '3 ★ passive'
    ELSE                           '4-5 ★ promoter'
  END AS review_bucket,
  -- 0..N months between this order and the customer's first order (for cohort use off v_orders)
  (EXTRACT(YEAR FROM order_month) - EXTRACT(YEAR FROM cohort_month)) * 12
    + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month)) AS months_since_first
FROM windowed
