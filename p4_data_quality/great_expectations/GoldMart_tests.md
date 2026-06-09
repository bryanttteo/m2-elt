# Schema tests in yaml
```
## 1. Revenue sanity check — no negative prices after validation
- name: price
  tests:
    - dbt_expectations.expect_column_values_to_be_between:
        min_value: 0
        severity: warn

## 2. Delivery date logic — delivered date must be after purchase date
- name: order_delivered_customer_date
  tests:
    - dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B:
        column_A: order_delivered_customer_date
        column_B: order_purchase_timestamp
        or_equal: false
        row_condition: "order_delivered_customer_date IS NOT NULL"
        severity: warn

## 3. Review score must be 1-5
- name: review_score   # add to dim_reviews schema
  tests:
    - dbt_expectations.expect_column_values_to_be_between:
        min_value: 1
        max_value: 5

## 4. Payment value must be positive
- name: payment_value
  tests:
    - dbt_expectations.expect_column_values_to_be_between:
        min_value: 0
        row_condition: "payment_value IS NOT NULL"
        severity: warn
```

# Standalone Tests
```
-- tests/assert_delivered_orders_have_delivery_date.sql
-- Every delivered order must have a delivery timestamp
SELECT id
FROM {{ ref('fact_orders_stage') }}
WHERE order_status = 'delivered'
    AND order_delivered_customer_date IS NULL

-- tests/assert_no_future_purchase_dates.sql
-- No order should be purchased in the future
SELECT id
FROM {{ ref('fact_orders_stage') }}
WHERE order_purchase_timestamp > CURRENT_TIMESTAMP()

-- tests/assert_high_value_orders_have_payment.sql
-- Orders over R$1000 should always have payment info
SELECT id
FROM {{ ref('fact_orders_stage') }}
WHERE price > 1000
    AND has_missing_payment_info = TRUE
```