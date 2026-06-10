"""Configuration for the Olist review-text analysis app.

Resolves BigQuery project / dataset / credentials from the repo-root ``.env.<ENV>``
files (the same convention the rest of the pipeline uses). Select the environment with
``ENV=prod`` (default) / ``ENV=dev`` / ``ENV=<name>``.

This app always queries BigQuery live (results are cached in-session via
``st.cache_data``); there is no offline parquet snapshot mode.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# wordcloud/ -> p5_analytics/ -> m2-elt/ (repo root holds the .env.<env> files and secrets/).
APP_DIR = Path(__file__).resolve().parent
# In a container the app lives at /app with no grandparent, so fall back gracefully
# (config then comes from real environment variables instead of an .env file).
REPO_ROOT = APP_DIR.parents[1] if len(APP_DIR.parents) > 1 else APP_DIR

ENV = os.environ.get("ENV", "prod")

# Load repo-root .env.<env> if present (local dev). On Cloud Run there is no .env file;
# config comes from real environment variables instead, so a missing file is fine.
_env_file = REPO_ROOT / f".env.{ENV}"
if _env_file.exists():
    load_dotenv(_env_file)

GCP_PROJECT = os.environ.get("GCP_PROJECT", "sctp-team2-project2-elt")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")
GOLD_DATASET = os.environ.get("BQ_GOLD_DATASET", "olist_gold_mart_prod")


def table(name: str) -> str:
    """Fully-qualified table ref used across queries.py."""
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
