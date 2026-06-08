{{ dbt_utils.deduplicate(
    relation=ref('dim_sellers'), 
    partition_by='id',
    order_by='seller_zip_code_prefix'
) }}