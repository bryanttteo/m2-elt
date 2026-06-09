-- snapshots/cleaned_data_snapshot.sql

{% snapshot cleaned_data_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='id',
        strategy='timestamp',
        updated_at='cleaned_at',
        invalidate_hard_deletes=True
    )
}}

SELECT * FROM {{ ref('fact_orders_stage') }}

{% endsnapshot %}