"""Pandas derivations on top of the cached BigQuery result sets.

Everything the charts need is computed here so the view modules stay declarative.
Retention concepts (order sequence, cohort, RFM) are computed on the *full* order
history; the date/state filters then subset which orders a chart displays.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import bq
import queries

# ---- delivery / review bucket definitions (shared so labels stay consistent) ----
DELIVERY_BUCKETS = ["Early / on-time", "1-3 days late", "4-7 days late", "8+ days late"]
REVIEW_BUCKETS = ["1-2 ★ (detractor)", "3 ★ (passive)", "4-5 ★ (promoter)"]


def _delivery_bucket(days_vs_estimate: float) -> str | float:
    if pd.isna(days_vs_estimate):
        return np.nan
    if days_vs_estimate <= 0:
        return DELIVERY_BUCKETS[0]
    if days_vs_estimate <= 3:
        return DELIVERY_BUCKETS[1]
    if days_vs_estimate <= 7:
        return DELIVERY_BUCKETS[2]
    return DELIVERY_BUCKETS[3]


def _review_bucket(score: float) -> str | float:
    if pd.isna(score):
        return np.nan
    if score <= 2:
        return REVIEW_BUCKETS[0]
    if score == 3:
        return REVIEW_BUCKETS[1]
    return REVIEW_BUCKETS[2]


_DATA: dict | None = None


def get_data(force: bool = False) -> dict:
    """Load + enrich the order history once; memoized for the process."""
    global _DATA
    if _DATA is not None and not force:
        return _DATA

    orders = bq.cached("orders", queries.ORDERS_SQL, force=force).copy()
    category = bq.cached("category", queries.CATEGORY_SQL, force=force).copy()

    orders["order_month"] = pd.to_datetime(orders["order_month"])
    orders["purchase_ts"] = pd.to_datetime(orders["purchase_ts"])

    # Order sequence per real person (customer_unique_id).
    orders = orders.sort_values("purchase_ts")
    grp = orders.groupby("customer_unique_id")
    orders["order_seq"] = grp.cumcount() + 1
    orders["cust_total_orders"] = grp["order_id"].transform("count")
    orders["is_repeat_order"] = orders["order_seq"] > 1
    orders["has_subsequent_order"] = orders["order_seq"] < orders["cust_total_orders"]
    # Cohort = month of the customer's first order.
    orders["cohort_month"] = grp["order_month"].transform("min")

    orders["is_delivered"] = orders["order_status"].eq("delivered")
    orders["is_late"] = orders["days_vs_estimate"] > 0
    orders["delivery_bucket"] = orders["days_vs_estimate"].apply(_delivery_bucket)
    orders["review_bucket"] = orders["review_score"].apply(_review_bucket)

    category["order_month"] = pd.to_datetime(category["order_month"])

    _DATA = {"orders": orders, "category": category}
    return _DATA


# ---------------------------------------------------------------- filters ----
def month_bounds() -> tuple[pd.Timestamp, pd.Timestamp]:
    o = get_data()["orders"]
    return o["order_month"].min(), o["order_month"].max()


def states() -> list[str]:
    o = get_data()["orders"]
    return sorted(o["customer_state"].dropna().unique().tolist())


def apply_filters(df: pd.DataFrame, start=None, end=None, sel_states=None) -> pd.DataFrame:
    out = df
    if start is not None:
        out = out[out["order_month"] >= pd.to_datetime(start)]
    if end is not None:
        out = out[out["order_month"] <= pd.to_datetime(end)]
    if sel_states:
        out = out[out["customer_state"].isin(sel_states)]
    return out


# --------------------------------------------------------------- headline ----
def kpis(df: pd.DataFrame) -> dict:
    gmv = df["gmv"].sum()
    n_orders = df["order_id"].nunique()
    n_customers = df["customer_unique_id"].nunique()
    repeat_customers = (
        df.groupby("customer_unique_id")["order_id"].nunique().gt(1).sum()
    )
    repeat_rate = repeat_customers / n_customers if n_customers else 0
    aov = gmv / n_orders if n_orders else 0
    deliv = df[df["is_delivered"] & df["days_vs_estimate"].notna()]
    on_time = (deliv["days_vs_estimate"] <= 0).mean() if len(deliv) else np.nan
    avg_review = df["review_score"].mean()
    avg_lead = df.loc[df["delivery_days"].notna(), "delivery_days"].mean()
    return {
        "gmv": gmv,
        "orders": n_orders,
        "customers": n_customers,
        "aov": aov,
        "repeat_rate": repeat_rate,
        "on_time_rate": on_time,
        "avg_review": avg_review,
        "avg_lead_days": avg_lead,
    }


# --------------------------------------------------------------- overview ----
def gmv_monthly(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["order_month", "is_repeat_order"])
        .agg(gmv=("gmv", "sum"), orders=("order_id", "nunique"))
        .reset_index()
    )
    pivot = g.pivot_table(
        index="order_month", columns="is_repeat_order", values="gmv", fill_value=0
    )
    pivot = pivot.rename(columns={False: "new_gmv", True: "repeat_gmv"})
    for col in ("new_gmv", "repeat_gmv"):
        if col not in pivot:
            pivot[col] = 0.0
    pivot["total_gmv"] = pivot["new_gmv"] + pivot["repeat_gmv"]
    orders_m = df.groupby("order_month")["order_id"].nunique().rename("orders")
    return pivot.join(orders_m).reset_index()


def repeat_rate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("order_month").agg(
        orders=("order_id", "nunique"),
        repeat_orders=("is_repeat_order", "sum"),
    )
    g["repeat_order_share"] = g["repeat_orders"] / g["orders"]
    return g.reset_index()


# -------------------------------------------------------------- retention ----
def cohort_matrix(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["cohort_month", "order_month"]).copy()
    d["months_since"] = (
        (d["order_month"].dt.year - d["cohort_month"].dt.year) * 12
        + (d["order_month"].dt.month - d["cohort_month"].dt.month)
    )
    sizes = d[d["months_since"] == 0].groupby("cohort_month")["customer_unique_id"].nunique()
    active = (
        d.groupby(["cohort_month", "months_since"])["customer_unique_id"]
        .nunique()
        .reset_index()
    )
    active = active.merge(sizes.rename("cohort_size"), on="cohort_month")
    active["retention"] = active["customer_unique_id"] / active["cohort_size"]
    mat = active.pivot(index="cohort_month", columns="months_since", values="retention")
    return mat


def orders_per_customer(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby("customer_unique_id")["order_id"].nunique()
    dist = counts.value_counts().sort_index().rename("customers").reset_index()
    dist.columns = ["orders_placed", "customers"]
    dist["orders_placed"] = dist["orders_placed"].astype(int)
    dist.loc[dist["orders_placed"] >= 5, "orders_placed"] = 5  # bucket the long tail
    dist = dist.groupby("orders_placed", as_index=False)["customers"].sum()
    dist["label"] = dist["orders_placed"].apply(lambda x: "5+" if x >= 5 else str(x))
    return dist


def rfm(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["purchase_ts"].max()
    agg = df.groupby("customer_unique_id").agg(
        recency=("purchase_ts", lambda s: (snapshot - s.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("gmv", "sum"),
    )
    # Segment with a simple, readable rule set.
    def seg(row):
        if row["frequency"] >= 2 and row["recency"] <= 120:
            return "Champions / Loyal"
        if row["frequency"] >= 2:
            return "Lapsing repeat"
        if row["recency"] <= 90:
            return "New / recent (one-off)"
        if row["recency"] <= 240:
            return "Cooling one-off"
        return "Dormant one-off"
    agg["segment"] = agg.apply(seg, axis=1)
    out = (
        agg.groupby("segment")
        .agg(customers=("frequency", "size"), monetary=("monetary", "sum"))
        .reset_index()
    )
    out["share"] = out["customers"] / out["customers"].sum()
    return out.sort_values("customers", ascending=False)


# --------------------------------------------------------------- delivery ----
def delivery_distribution(df: pd.DataFrame) -> pd.Series:
    return df.loc[df["delivery_days"].notna() & (df["delivery_days"] >= 0), "delivery_days"]


def ontime_by_state(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["is_delivered"] & df["days_vs_estimate"].notna()]
    g = d.groupby("customer_state").agg(
        orders=("order_id", "nunique"),
        late=("is_late", "sum"),
    )
    g["late_rate"] = g["late"] / g["orders"]
    return g.reset_index()


def review_distribution(df: pd.DataFrame) -> pd.DataFrame:
    g = df.dropna(subset=["review_score"]).groupby("review_score")["order_id"].nunique()
    return g.rename("orders").reset_index()


def review_by_delivery_bucket(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["delivery_bucket", "review_score"])
    g = d.groupby("delivery_bucket").agg(
        avg_review=("review_score", "mean"),
        orders=("order_id", "nunique"),
    ).reindex(DELIVERY_BUCKETS).dropna(how="all").reset_index()
    return g


def late_rate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["is_delivered"] & df["days_vs_estimate"].notna()]
    g = d.groupby("order_month").agg(
        orders=("order_id", "nunique"), late=("is_late", "sum")
    )
    g["late_rate"] = g["late"] / g["orders"]
    return g.reset_index()


# -------------------------------------------------------------- diagnosis ----
def reorder_by_review_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Share of orders followed by another order from the same customer, by review."""
    d = df.dropna(subset=["review_bucket"])
    g = d.groupby("review_bucket").agg(
        reorder_rate=("has_subsequent_order", "mean"),
        orders=("order_id", "nunique"),
    ).reindex(REVIEW_BUCKETS).dropna(how="all").reset_index()
    return g


def acquisition_treadmill(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly new vs returning customers — visualises the acquisition treadmill."""
    g = (
        df.groupby(["order_month", "is_repeat_order"])["customer_unique_id"]
        .nunique()
        .reset_index()
    )
    pivot = g.pivot_table(index="order_month", columns="is_repeat_order",
                          values="customer_unique_id", fill_value=0)
    pivot = pivot.rename(columns={False: "new", True: "repeat"})
    for c in ("new", "repeat"):
        if c not in pivot:
            pivot[c] = 0
    return pivot.reset_index()


def reorder_by_delivery_bucket(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["delivery_bucket"])
    g = d.groupby("delivery_bucket").agg(
        reorder_rate=("has_subsequent_order", "mean"),
        orders=("order_id", "nunique"),
    ).reindex(DELIVERY_BUCKETS).dropna(how="all").reset_index()
    return g


# ---------------------------------------------------------------- catalog ----
def top_categories(cat: pd.DataFrame, start=None, end=None, sel_states=None, n=12) -> pd.DataFrame:
    d = cat
    if start is not None:
        d = d[d["order_month"] >= pd.to_datetime(start)]
    if end is not None:
        d = d[d["order_month"] <= pd.to_datetime(end)]
    if sel_states:
        d = d[d["customer_state"].isin(sel_states)]
    g = d.groupby("product_category").agg(
        gmv=("gmv", "sum"), items=("n_items", "sum")
    ).reset_index().sort_values("gmv", ascending=False).head(n)
    return g


# -------------------------------------------------------------- scenario -----
def cac_scenario(k: dict, monthly_spend: float, target_cac: float, repeat_uplift_pp: float) -> dict:
    """Illustrative unit economics. NOT warehouse data — driven by user assumptions.

    Uses observed GMV / orders / customers / repeat-rate (``k`` from ``kpis``) plus
    the CEO's assumed marketing spend to derive blended CAC, acquisition intensity, and
    the GMV upside of lifting the repeat rate.
    """
    n_months = max(k.get("_n_months", 1), 1)
    total_spend = monthly_spend * n_months
    gmv = k["gmv"]
    customers = k["customers"]
    aov = k["aov"]
    repeat_rate = k["repeat_rate"]

    blended_cac = total_spend / customers if customers else np.nan
    pct_gmv_on_marketing = total_spend / gmv if gmv else np.nan
    # Extra repeat customers from a +Δpp repeat rate, each worth ~1 more order at AOV.
    extra_repeat_customers = customers * (repeat_uplift_pp / 100.0)
    incremental_gmv = extra_repeat_customers * aov
    # Acquiring that GMV via paid instead would cost (incremental orders / AOV)*CAC.
    equiv_paid_cost = extra_repeat_customers * (target_cac if target_cac else blended_cac)
    return {
        "total_spend": total_spend,
        "blended_cac": blended_cac,
        "pct_gmv_on_marketing": pct_gmv_on_marketing,
        "repeat_rate": repeat_rate,
        "incremental_gmv": incremental_gmv,
        "extra_repeat_customers": extra_repeat_customers,
        "equiv_paid_cost": equiv_paid_cost,
    }
