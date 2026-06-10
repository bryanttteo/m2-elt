"""SQL against the Olist gold mart, parameterized by the configured dataset.

Design choice: instead of many pre-aggregated cubes (which break distinct-count metrics
like repeat rate once you filter), we pull two modest result sets once and do all
filtering / derivation in pandas (see metrics.py):

* ``orders``   — one row per order (~99k), the workhorse for KPIs, GMV, retention,
                 delivery and review-correlation charts.
* ``category`` — item revenue by (month, state, product_category) for the catalog views.

Both are cached to parquet, so this runs at most once per snapshot.
"""
from __future__ import annotations

import config

F = config.table("fact_orders")
DC = config.table("dim_customers")
DR = config.table("dim_reviews")
DP = config.table("dim_products")

# One row per order. GMV = SUM(price) at item grain collapsed to the order; freight kept
# separate. Payment + status taken with ANY_VALUE (constant within an order). Review score
# is the single (latest) review per order from dim_reviews.
ORDERS_SQL = f"""
WITH ord AS (
  SELECT
    id                                   AS order_id,
    ANY_VALUE(customer_id)               AS customer_id,
    ANY_VALUE(order_status)              AS order_status,
    ANY_VALUE(order_purchase_timestamp)  AS purchase_ts,
    ANY_VALUE(order_delivered_customer_date) AS delivered_ts,
    ANY_VALUE(order_estimated_delivery_date) AS estimated_ts,
    SUM(price)                           AS gmv,
    SUM(freight_value)                   AS freight,
    COUNT(*)                             AS n_items,
    ANY_VALUE(payment_type)              AS payment_type,
    MAX(payment_installments)            AS payment_installments
  FROM {F}
  WHERE order_purchase_timestamp IS NOT NULL
  GROUP BY id
)
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
LEFT JOIN {DC} c ON o.customer_id = c.id
LEFT JOIN {DR} r ON o.order_id    = r.id
"""

# Item revenue by month / state / category for catalog charts.
CATEGORY_SQL = f"""
SELECT
  DATE(DATE_TRUNC(DATE(f.order_purchase_timestamp), MONTH)) AS order_month,
  c.customer_state,
  COALESCE(p.product_category, 'unknown') AS product_category,
  SUM(f.price)  AS gmv,
  COUNT(*)      AS n_items
FROM {F} f
LEFT JOIN {DP} p ON f.product_id  = p.id
LEFT JOIN {DC} c ON f.customer_id = c.id
WHERE f.order_purchase_timestamp IS NOT NULL
GROUP BY 1, 2, 3
"""

QUERIES = {
    "orders": ORDERS_SQL,
    "category": CATEGORY_SQL,
}
