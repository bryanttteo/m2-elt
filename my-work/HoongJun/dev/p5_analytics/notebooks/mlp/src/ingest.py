"""Data ingestion — pull one row per ORDER from the BigQuery gold mart.

Auth mirrors the EDA notebook: service-account keyfile first, fall back to gcloud
ADC if the key is missing/rotated. The fact is at order-ITEM grain, so we aggregate
up to order grain here (the unit a logistics team acts on). Item-level dimensions
(category, seller state) are reduced with APPROX_TOP_COUNT (the modal value per order).

Only columns knowable at/just after order time are pulled — actual delivery and
carrier dates are kept ONLY to build the label, never as features (see features.py).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import resolve_path

# Timestamp columns we parse to datetime after the pull.
_TS_COLS = ["purchase_ts", "approved_ts", "delivered_ts", "estimated_ts"]


def _order_grain_sql(gold: str) -> str:
    return f"""
    WITH items AS (
      SELECT
        f.id                              AS order_id,
        f.customer_id,
        f.seller_id,
        f.order_status,
        f.order_purchase_timestamp        AS purchase_ts,
        f.order_approved_at               AS approved_ts,
        f.order_delivered_customer_date   AS delivered_ts,
        f.order_estimated_delivery_date   AS estimated_ts,
        f.price,
        f.freight_value,
        p.product_category,
        p.product_weight_g,
        p.product_length_cm * p.product_height_cm * p.product_width_cm AS volume_cm3,
        s.seller_state
      FROM `{gold}.fact_orders` f
      LEFT JOIN `{gold}.dim_products` p ON f.product_id = p.id
      LEFT JOIN `{gold}.dim_sellers`  s ON f.seller_id  = s.id
    ),
    order_grain AS (
      SELECT
        order_id,
        ANY_VALUE(customer_id)            AS customer_id,
        ANY_VALUE(order_status)           AS order_status,
        ANY_VALUE(purchase_ts)            AS purchase_ts,
        ANY_VALUE(approved_ts)            AS approved_ts,
        ANY_VALUE(delivered_ts)           AS delivered_ts,
        ANY_VALUE(estimated_ts)           AS estimated_ts,
        SUM(price)                        AS order_gmv,
        SUM(freight_value)                AS order_freight,
        COUNT(*)                          AS item_count,
        COUNT(DISTINCT seller_id)         AS seller_count,
        SUM(product_weight_g)             AS total_weight_g,
        MAX(volume_cm3)                   AS max_volume_cm3,
        APPROX_TOP_COUNT(product_category, 1)[OFFSET(0)].value AS product_category,
        APPROX_TOP_COUNT(seller_state, 1)[OFFSET(0)].value     AS seller_state
      FROM items
      GROUP BY order_id
    )
    SELECT
      g.*,
      c.customer_unique_id,
      c.customer_state
    FROM order_grain g
    LEFT JOIN `{gold}.dim_customers` c ON g.customer_id = c.id
    """


def make_client(cfg: dict):
    """BigQuery client: keyfile first (smoke-tested), else gcloud ADC."""
    from google.cloud import bigquery

    project = cfg["bigquery"]["project"]
    keyfile = resolve_path(cfg, cfg["bigquery"]["keyfile"])
    if keyfile.exists():
        try:
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(str(keyfile))
            client = bigquery.Client(credentials=creds, project=project)
            client.query("SELECT 1").result()
            print(f"✅ Authenticated with service-account keyfile: {keyfile.name}")
            return client
        except Exception as e:  # noqa: BLE001 — any auth failure -> ADC fallback
            print(f"⚠️  Keyfile unusable ({str(e)[:60]}...). Falling back to gcloud ADC.")
    client = bigquery.Client(project=project)
    client.query("SELECT 1").result()
    print("✅ Authenticated with gcloud Application Default Credentials (ADC).")
    return client


def load_data(cfg: dict) -> pd.DataFrame:
    """Return the order-grain DataFrame, reading a parquet cache if available."""
    bq = cfg["bigquery"]
    cache = resolve_path(cfg, bq["cache_path"]) if bq.get("cache_path") else None

    if bq.get("use_cache") and cache and cache.exists():
        print(f"📦 Loading cached order-grain table: {cache}")
        df = pd.read_parquet(cache)
    else:
        gold = f"{bq['project']}.{bq['gold_dataset']}"
        print(f"🔌 Querying BigQuery gold mart: {gold}.fact_orders (order grain)")
        client = make_client(cfg)
        df = client.query(_order_grain_sql(gold)).to_dataframe()
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
            print(f"💾 Cached {len(df):,} orders -> {cache}")

    for col in _TS_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)
    print(f"✅ Loaded {len(df):,} orders, {df.shape[1]} columns.")
    return df
