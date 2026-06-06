{#
    Use the custom `+schema` (i.e. BigQuery dataset) verbatim instead of dbt's
    default `<target_schema>_<custom_schema>` concatenation. This lets us drive
    each layer's dataset straight from env vars (olist_bronze_dev / olist_stage_dev
    / olist_gold_mart_dev) without a target-name prefix bleeding in.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
