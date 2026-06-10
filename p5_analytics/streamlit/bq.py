"""BigQuery access layer with a parquet cache.

``cached(name, sql)`` returns a DataFrame for a named query. Resolution order:

1. In-process memo (so repeated callbacks in one session never re-read disk/BQ).
2. ``data/<name>.parquet`` on disk, if it exists and is within ``CACHE_TTL`` (or
   ``OFFLINE`` mode, where the parquet is the only source of truth).
3. A live BigQuery job (writes the result back to the parquet cache).

This keeps the app instant after first load, makes BigQuery cost trivial, and lets us
bake a fully self-contained snapshot image (``DASH_OFFLINE=1``) for the live demo.
"""
from __future__ import annotations

import time
from pathlib import Path

import db_dtypes  # noqa: F401  registers the BigQuery DATE ('dbdate') dtype for parquet round-trips
import pandas as pd

import config

_MEMO: dict[str, pd.DataFrame] = {}
_client = None


def _bq_client():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=config.GCP_PROJECT, location=config.BQ_LOCATION)
    return _client


def _parquet_path(name: str) -> Path:
    return config.DATA_DIR / f"{name}.parquet"


def _fresh(path: Path) -> bool:
    if not path.exists():
        return False
    if config.OFFLINE or config.CACHE_TTL == 0:
        return True
    return (time.time() - path.stat().st_mtime) < config.CACHE_TTL


def cached(name: str, sql: str, force: bool = False) -> pd.DataFrame:
    """Return the result of ``sql`` as a DataFrame, using the parquet cache."""
    if not force and name in _MEMO:
        return _MEMO[name]

    path = _parquet_path(name)
    if not force and _fresh(path):
        df = pd.read_parquet(path)
        _MEMO[name] = df
        return df

    if config.OFFLINE:
        raise RuntimeError(
            f"OFFLINE mode but no snapshot for '{name}' at {path}. "
            f"Run `make snapshot` (with BigQuery access) first."
        )

    df = _bq_client().query(sql).result().to_dataframe()
    df.to_parquet(path, index=False)
    _MEMO[name] = df
    return df


def refresh_all(queries: dict[str, str]) -> None:
    """Force-rebuild every parquet in ``queries`` (used by `make snapshot`)."""
    for name, sql in queries.items():
        print(f"  querying {name} ...", flush=True)
        cached(name, sql, force=True)
    print(f"snapshot written to {config.DATA_DIR}", flush=True)
