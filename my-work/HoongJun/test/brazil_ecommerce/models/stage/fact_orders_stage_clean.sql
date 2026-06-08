{{ dbt_utils.deduplicate(
    relation=ref('fact_orders_stage'), 
    partition_by='id',
    order_by='order_purchase_timestamp desc'
) }}