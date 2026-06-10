"""Feature engineering — derive order-time features and build the preprocessor.

EVERY feature here is knowable at order time. Actual delivery/carrier dates and the
review score are deliberately excluded to prevent target leakage (see plan §A.3).

EDA links (mlp-plan-result.md §A.3):
  * customer_state / seller_state  -> late rate is geographically concentrated
  * same_state / freight / weight  -> distance & bulk drive lead time
  * estimated_lead_days            -> the promise itself encodes route difficulty
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Columns that must NEVER become features (outcome / identity / raw timestamps).
LEAK_COLS = ["delivered_ts", "approved_ts", "order_status"]
ID_COLS = ["order_id", "customer_id", "customer_unique_id"]

NUMERIC = [
    "order_gmv", "order_freight", "item_count", "seller_count",
    "total_weight_g", "max_volume_cm3", "estimated_lead_days",
    "purchase_dow", "purchase_month", "purchase_hour", "freight_ratio",
]
CATEGORICAL = ["customer_state", "seller_state", "product_category", "same_state"]


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Derive model-ready columns from the raw order-grain frame."""
    out = df.copy()
    purchase = out["purchase_ts"]
    # The promised lead time the customer was quoted (days from purchase to estimate).
    out["estimated_lead_days"] = (out["estimated_ts"] - purchase).dt.total_seconds() / 86400
    out["purchase_dow"] = purchase.dt.dayofweek
    out["purchase_month"] = purchase.dt.month
    out["purchase_hour"] = purchase.dt.hour
    # Shipping cost relative to basket value — a distance/bulk proxy.
    out["freight_ratio"] = out["order_freight"] / out["order_gmv"].replace(0, np.nan)
    # Same-state shipments are structurally faster than cross-state ones.
    out["same_state"] = np.where(
        out["customer_state"].notna() & (out["customer_state"] == out["seller_state"]),
        "same", "cross",
    )
    return out


def split_X_y(df: pd.DataFrame):
    """Return (X with feature columns only, y) — drops ids, leaks and the label."""
    y = df["label"]
    X = df[[c for c in NUMERIC + CATEGORICAL if c in df.columns]].copy()
    return X, y


def build_preprocessor() -> ColumnTransformer:
    """ColumnTransformer: median-impute+scale numerics, impute+one-hot categoricals."""
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        # sparse_output=False -> dense, required by HistGradientBoosting.
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=50,
                                 sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC),
        ("cat", categorical, CATEGORICAL),
    ], remainder="drop")


def feature_table() -> pd.DataFrame:
    """Human-readable summary of how each feature is handled (for the notebook/docs)."""
    rows = [(c, "numeric", "median impute + StandardScaler") for c in NUMERIC]
    rows += [(c, "categorical", "most_frequent impute + OneHot(min_freq=50)") for c in CATEGORICAL]
    return pd.DataFrame(rows, columns=["feature", "type", "processing"])
