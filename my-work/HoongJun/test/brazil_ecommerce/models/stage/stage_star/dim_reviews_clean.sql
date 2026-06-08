{{ dbt_utils.deduplicate(
    relation=ref('dim_reviews'), 
    partition_by='id',
    order_by='review_answer_timestamp DESC'
) }}