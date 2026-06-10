-- v_cohort_retention — long-form cohort retention for the Superset heatmap.
-- One row per (cohort_month, months_since): share of the cohort's customers who placed
-- an order that many months after their first. Mirrors metrics.cohort_matrix().
WITH ord AS (
  SELECT
    id                                  AS order_id,
    ANY_VALUE(customer_id)              AS customer_id,
    ANY_VALUE(order_purchase_timestamp) AS purchase_ts
  FROM `{{PROJECT}}.{{GOLD}}.fact_orders`
  WHERE order_purchase_timestamp IS NOT NULL
  GROUP BY id
),
joined AS (
  SELECT o.order_id, c.customer_unique_id,
         DATE(DATE_TRUNC(DATE(o.purchase_ts), MONTH)) AS order_month
  FROM ord o
  LEFT JOIN `{{PROJECT}}.{{GOLD}}.dim_customers` c ON o.customer_id = c.id
),
cohorts AS (
  SELECT *,
    MIN(order_month) OVER (PARTITION BY customer_unique_id) AS cohort_month
  FROM joined
),
ms AS (
  SELECT
    cohort_month,
    customer_unique_id,
    (EXTRACT(YEAR FROM order_month) - EXTRACT(YEAR FROM cohort_month)) * 12
      + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month)) AS months_since
  FROM cohorts
),
sizes AS (
  SELECT cohort_month, COUNT(DISTINCT customer_unique_id) AS cohort_size
  FROM ms WHERE months_since = 0 GROUP BY cohort_month
),
active AS (
  SELECT cohort_month, months_since,
         COUNT(DISTINCT customer_unique_id) AS active_customers
  FROM ms GROUP BY cohort_month, months_since
)
SELECT
  a.cohort_month,
  CAST(a.months_since AS STRING) AS months_since,
  a.months_since                 AS months_since_num,
  a.active_customers,
  s.cohort_size,
  SAFE_DIVIDE(a.active_customers, s.cohort_size) AS retention
FROM active a
JOIN sizes s USING (cohort_month)
WHERE a.months_since >= 0
