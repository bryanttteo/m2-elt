"""Superset configuration — Olist executive dashboard.

Mounted into the container at /app/pythonpath/superset_config.py. Keeps the metadata DB
on Postgres, caching on Redis, and reads secrets from the environment. The BigQuery
connection itself authenticates via GOOGLE_APPLICATION_CREDENTIALS (ADC), so no key
material is stored in Superset's metadata DB.
"""
import os

# ── Secret key (sign cookies / encrypt stored connection extras) ───────────────
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# ── Metadata database (dashboards, charts, users) → external Postgres ─────────
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASS']}"
    f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
)

# ── Caching — Redis. This is the real performance lever in the cloud: identical
#    chart queries are served from cache instead of re-hitting BigQuery. BigQuery's
#    own 24h result cache sits underneath this for free. ──────────────────────────
_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


def _cache(db: int, prefix: str) -> dict:
    return {
        "CACHE_TYPE": "RedisCache",
        "CACHE_DEFAULT_TIMEOUT": 60 * 60,        # 1h
        "CACHE_KEY_PREFIX": prefix,
        "CACHE_REDIS_HOST": _REDIS_HOST,
        "CACHE_REDIS_PORT": _REDIS_PORT,
        "CACHE_REDIS_DB": db,
    }


CACHE_CONFIG = _cache(1, "superset_")
DATA_CACHE_CONFIG = _cache(2, "superset_data_")
FILTER_STATE_CACHE_CONFIG = _cache(3, "superset_filter_")
EXPLORE_FORM_DATA_CACHE_CONFIG = _cache(4, "superset_explore_")

# ── Query limits / behaviour ──────────────────────────────────────────────────
ROW_LIMIT = 100_000          # v_orders is ~99k rows; allow the full base set
SQL_MAX_ROW = 100_000
SUPERSET_WEBSERVER_TIMEOUT = 120

# Synchronous queries only — no Celery worker in this deployment (keeps Cloud Run /
# single-VM simple). Async SQL Lab is therefore disabled.
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Allow embedding the dashboard in the M7 deck / an iframe if needed.
ENABLE_PROXY_FIX = True
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.core.log"]
