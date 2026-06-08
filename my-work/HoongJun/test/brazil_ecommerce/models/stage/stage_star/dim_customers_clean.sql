{{ dbt_utils.deduplicate(
    relation=ref('dim_customers'), 
    partition_by='id',
    order_by='customer_zip_code_prefix'
) }}