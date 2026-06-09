-- snapshots/snap_sellers.sql

{% snapshot snap_sellers %}
{{
    config(
        target_schema='snapshots',
        unique_key='id',
        strategy='check',
        check_cols=['seller_city', 'seller_state', 'seller_zip_code_prefix', 'zip_codes_match'],
    )
}}
SELECT * FROM {{ ref('dim_sellers') }}
{% endsnapshot %}