-- v_customers — customer-grain (one row per real person = customer_unique_id).
-- Powers the repeat-customer rate Big Number, RFM segment breakdown, and the
-- orders-per-customer distribution. Mirrors metrics.rfm() segment rules.
-- snapshot date = the latest purchase timestamp in the warehouse (recency reference).
WITH ord AS (
  SELECT
    id                                   AS order_id,
    ANY_VALUE(customer_id)               AS customer_id,
    ANY_VALUE(order_purchase_timestamp)  AS purchase_ts,
    SUM(price)                           AS gmv
  FROM `{{PROJECT}}.{{GOLD}}.fact_orders`
  WHERE order_purchase_timestamp IS NOT NULL
  GROUP BY id
),
joined AS (
  SELECT o.order_id, o.purchase_ts, o.gmv, c.customer_unique_id, c.customer_state
  FROM ord o
  LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_customers` c ON o.customer_id = c.id
),
snap AS (SELECT MAX(purchase_ts) AS snapshot_ts FROM joined),
agg AS (
  SELECT
    j.customer_unique_id,
    ANY_VALUE(j.customer_state)                                          AS customer_state,
    COUNT(DISTINCT j.order_id)                                           AS frequency,
    SUM(j.gmv)                                                           AS monetary,
    MIN(DATE(j.purchase_ts))                                            AS first_order_date,
    DATE_DIFF(DATE((SELECT snapshot_ts FROM snap)), DATE(MAX(j.purchase_ts)), DAY) AS recency_days
  FROM joined j
  GROUP BY j.customer_unique_id
)
SELECT
  customer_unique_id,
  customer_state,
  frequency,
  monetary,
  recency_days,
  first_order_date,
  DATE(DATE_TRUNC(first_order_date, MONTH)) AS cohort_month,
  frequency > 1 AS is_repeat_customer,
  -- bucket the long tail at 5+ for the orders-per-customer distribution chart
  CASE WHEN frequency >= 5 THEN '5+' ELSE CAST(frequency AS STRING) END AS orders_placed_bucket,
  -- readable RFM segments (same rule set as p5_analytics/dash/metrics.py rfm())
  CASE
    WHEN frequency >= 2 AND recency_days <= 120 THEN 'Champions / Loyal'
    WHEN frequency >= 2                          THEN 'Lapsing repeat'
    WHEN recency_days <= 90                       THEN 'New / recent (one-off)'
    WHEN recency_days <= 240                      THEN 'Cooling one-off'
    ELSE                                              'Dormant one-off'
  END AS segment
FROM agg
