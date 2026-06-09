-- snapshots/snap_products.sql

{% snapshot snap_products %}
{{
    config(
        target_schema='snapshots',
        unique_key='id',
        strategy='check',
        check_cols=[
            'product_category',
            'product_weight_g',
            'product_length_cm',
            'product_height_cm',
            'product_width_cm'
        ],
    )
}}
SELECT * FROM {{ ref('dim_products') }}
{% endsnapshot %}