"""Label construction for each learning task — leakage-aware.

late_delivery   : positive when an order arrived AFTER the promised date. Defined
                  only on delivered orders with both dates present (EDA scope).
repeat_purchase : positive when the customer (customer_unique_id) placed >1 order,
                  attributed to their FIRST order so all features are pre-outcome.
"""
from __future__ import annotations

import pandas as pd

LABEL = "label"


def _late_delivery(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["order_status"] == "delivered"].copy()
    out = out.dropna(subset=["delivered_ts", "estimated_ts", "purchase_ts"])
    out[LABEL] = (out["delivered_ts"] > out["estimated_ts"]).astype(int)
    return out


def _repeat_purchase(df: pd.DataFrame) -> pd.DataFrame:
    out = df.dropna(subset=["customer_unique_id", "purchase_ts"]).copy()
    counts = out.groupby("customer_unique_id")["order_id"].transform("count")
    # rank=1 -> the customer's first order; predict whether more follow.
    rank = out.groupby("customer_unique_id")["purchase_ts"].rank(method="first")
    first = out[rank == 1].copy()
    first[LABEL] = (counts[rank == 1] > 1).astype(int)
    return first


_BUILDERS = {"late_delivery": _late_delivery, "repeat_purchase": _repeat_purchase}


def make_labels(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Attach a 0/1 ``label`` column for the configured target and report balance."""
    target = cfg["target"]
    if target not in _BUILDERS:
        raise ValueError(f"Unknown target {target!r}; choose from {list(_BUILDERS)}")
    out = _BUILDERS[target](df).reset_index(drop=True)
    pos = out[LABEL].mean()
    print(f"🎯 Target '{target}': {len(out):,} rows, "
          f"{out[LABEL].sum():,} positive ({pos:.1%}).")
    return out
