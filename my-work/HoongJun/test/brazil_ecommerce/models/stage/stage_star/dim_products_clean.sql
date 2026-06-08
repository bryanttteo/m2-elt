{{ dbt_utils.deduplicate(
    relation=ref('dim_products'), 
    partition_by='id',
    order_by='product_name_lenght'
) }}