"""Configuration for the Olist executive dashboard.

Resolves BigQuery project / dataset / credentials from the repo-root ``.env.<ENV>``
files (the same convention the rest of the pipeline uses), so the dashboard is never
hardcoded to a single dataset. Select the environment with ``ENV=prod`` (default) /
``ENV=dev`` / ``ENV=<name>``.

When ``DASH_OFFLINE=1`` (the baked-snapshot / demo mode) BigQuery is never touched —
the app reads the parquet files under ``data/`` instead. See ``bq.py``.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# dash/ -> m2-elt/ (repo root holds the .env.<env> files and secrets/).
DASH_DIR = Path(__file__).resolve().parent
# Local layout: dash/ -> p5_analytics/ -> m2-elt/ (repo root). In a container the app lives
# at /app with no grandparent, so fall back gracefully (config then comes from env vars).
REPO_ROOT = DASH_DIR.parents[1] if len(DASH_DIR.parents) > 1 else DASH_DIR
DATA_DIR = DASH_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ENV = os.environ.get("ENV", "prod")

# Load repo-root .env.<env> if present (local dev). On Cloud Run there is no .env file;
# config comes from real environment variables instead, so a missing file is fine.
_env_file = REPO_ROOT / f".env.{ENV}"
if _env_file.exists():
    load_dotenv(_env_file)

GCP_PROJECT = os.environ.get("GCP_PROJECT", "sctp-team2-project2-elt")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")
GOLD_DATASET = os.environ.get("BQ_GOLD_DATASET", "olist_gold_mart_prod")

# Fully-qualified table refs used across queries.py.
def table(name: str) -> str:
    return f"`{GCP_PROJECT}.{GOLD_DATASET}.{name}`"


# Credentials: prefer an explicit keyfile path; make it absolute relative to repo root
# so the app can be launched from anywhere. On Cloud Run leave this unset and rely on the
# attached service-account (ADC).
_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if _cred:
    cred_path = Path(_cred)
    if not cred_path.is_absolute():
        cred_path = (REPO_ROOT / cred_path).resolve()
    if cred_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)

# Offline / demo mode: serve from baked parquet snapshot, never query BigQuery.
OFFLINE = os.environ.get("DASH_OFFLINE", "0") == "1"

# Cache freshness for the live-BQ path (seconds). 0 = always use cache if it exists.
CACHE_TTL = int(os.environ.get("DASH_CACHE_TTL", "0"))
