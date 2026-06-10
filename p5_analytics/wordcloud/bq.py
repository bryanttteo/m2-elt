"""BigQuery access layer (live, Streamlit-cached).

``run(sql)`` executes a query and returns a DataFrame. Results are memoized for the
session via ``st.cache_data`` so repeated reruns (Streamlit re-executes the whole script
on every widget change) never re-hit BigQuery for the same SQL.
"""
from __future__ import annotations

import db_dtypes  # noqa: F401  registers the BigQuery DATE ('dbdate') dtype for dataframes
import pandas as pd
import streamlit as st

import config

_client = None


def _bq_client():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=config.GCP_PROJECT, location=config.BQ_LOCATION)
    return _client


@st.cache_data(show_spinner="Querying BigQuery ...", ttl=3600)
def run(sql: str) -> pd.DataFrame:
    """Execute ``sql`` against BigQuery and return the result as a DataFrame."""
    return _bq_client().query(sql).result().to_dataframe()
