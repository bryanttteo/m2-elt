"""Central env-driven config for the Olist orchestration.

Loads the repo-root .env.<env> once (python-dotenv) and exposes the canonical
names. Importing this module first guarantees env vars are set before dbt's
`prepare_if_dev()` / BigQuery clients read them.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# .../p6_orchestration/olist_orchestration/olist_orchestration/config.py
#   parents[0] = olist_orchestration (pkg)
#   parents[1] = olist_orchestration (project)
#   parents[2] = p6_orchestration
#   parents[3] = m2-elt  (repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]

# OLIST_ENV selects which env file to load (dev|prod). Defaults to dev.
OLIST_ENV = os.getenv("OLIST_ENV", "dev")
_env_file = REPO_ROOT / f".env.{OLIST_ENV}"
if _env_file.exists():
    load_dotenv(_env_file)

# Resolve a possibly-relative keyfile path to an absolute one (relative paths in
# .env are written relative to the repo root, but the process cwd may differ).
_keyfile = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if _keyfile and not os.path.isabs(_keyfile):
    _abs = (REPO_ROOT / _keyfile).resolve()
    if _abs.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_abs)

# --- Canonical config (env first, sensible dev defaults) ---------------------
GCP_PROJECT = os.getenv("GCP_PROJECT", "sctp-team2-project2-elt")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")
BQ_BRONZE_DATASET = os.getenv("BQ_BRONZE_DATASET", "olist_bronze_dev")
BQ_STAGE_DATASET = os.getenv("BQ_STAGE_DATASET", "olist_stage_dev")
BQ_GOLD_DATASET = os.getenv("BQ_GOLD_DATASET", "olist_gold_mart_dev")

# Where raw CSVs live for the manual load path, and how to load bronze.
OLIST_DATA_DIR = Path(os.getenv("OLIST_DATA_DIR", str(REPO_ROOT / "datasets")))
if not OLIST_DATA_DIR.is_absolute():
    OLIST_DATA_DIR = (REPO_ROOT / OLIST_DATA_DIR).resolve()
# How to populate bronze. One of:
#   manual          - load datasets/*.csv straight into BQ via load jobs (default).
#   meltano_csv     - run the tap-csv -> target-bigquery pipeline (p1_el/meltano-raw-csv).
#   meltano_postgres- run the tap-postgres -> target-bigquery pipeline (p1_el/olist-meltano-pg).
# Legacy alias: "meltano" is treated as "meltano_csv" for backward compatibility.
BRONZE_LOAD_METHOD = os.getenv("BRONZE_LOAD_METHOD", "manual")
if BRONZE_LOAD_METHOD == "meltano":
    BRONZE_LOAD_METHOD = "meltano_csv"

DBT_DIR = REPO_ROOT / "p3_dbt_project" / "brazil_ecommerce"
# Two interchangeable Meltano projects feeding bronze, selected by BRONZE_LOAD_METHOD:
MELTANO_CSV_DIR = REPO_ROOT / "p1_el" / "meltano-raw-csv"      # tap-csv  (datasets/*.csv)
MELTANO_PG_DIR = REPO_ROOT / "p1_el" / "olist-meltano-pg"      # tap-postgres (Cloud SQL oltp)
# Backwards-compatible alias for code/tests that referenced the single MELTANO_DIR.
MELTANO_DIR = MELTANO_CSV_DIR

# dbt source name (from sources.yml) — used to build bronze asset keys that line
# up with the source assets dagster-dbt generates: AssetKey([source_name, table]).
DBT_SOURCE_NAME = "brazil_ecommerce"

# bronze table name (_raw layer) -> source CSV filename (file on disk is unchanged)
CSV_FILES = {
    "olist_customers_raw": "olist_customers_dataset.csv",
    "olist_geolocation_raw": "olist_geolocation_dataset.csv",
    "olist_order_items_raw": "olist_order_items_dataset.csv",
    "olist_order_payments_raw": "olist_order_payments_dataset.csv",
    "olist_order_reviews_raw": "olist_order_reviews_dataset.csv",
    "olist_orders_raw": "olist_orders_dataset.csv",
    "olist_products_raw": "olist_products_dataset.csv",
    "olist_sellers_raw": "olist_sellers_dataset.csv",
    "product_category_name_translation_raw": "product_category_name_translation.csv",
}
BRONZE_TABLES = list(CSV_FILES.keys())
