"""Superset config for Cloud Run.

Differences from the local config: metadata DB is the shared Cloud SQL Postgres reached
over the Cloud SQL unix socket; caching is in-process SimpleCache (no Redis sidecar on
Cloud Run); the server trusts the Cloud Run proxy. Single instance, synchronous queries.
"""
import os
from urllib.parse import quote_plus

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# ── Metadata DB — Cloud SQL Postgres via unix socket (/cloudsql/<conn>) ────────
_user = os.environ["DB_USER"]
_pw = quote_plus(os.environ["DB_PASS"])
_name = os.environ["DB_NAME"]
_socket = os.environ.get("DB_SOCKET")  # e.g. /cloudsql/proj:region:instance
if _socket:
    SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{_user}:{_pw}@/{_name}?host={_socket}"
else:  # fallback: TCP host
    _host = os.environ.get("DB_HOST", "127.0.0.1")
    _port = os.environ.get("DB_PORT", "5432")
    SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{_user}:{_pw}@{_host}:{_port}/{_name}"

# ── Caching — in-process (single Cloud Run instance) ──────────────────────────
_cache = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 60 * 60}
CACHE_CONFIG = _cache
DATA_CACHE_CONFIG = _cache
FILTER_STATE_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 24 * 3600}
EXPLORE_FORM_DATA_CACHE_CONFIG = FILTER_STATE_CACHE_CONFIG

ROW_LIMIT = 100_000
SQL_MAX_ROW = 100_000
SUPERSET_WEBSERVER_TIMEOUT = 120

FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Behind the Cloud Run HTTPS proxy.
ENABLE_PROXY_FIX = True
TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.core.log"]
