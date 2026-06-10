#!/usr/bin/env python3
"""Generate the Superset import bundle (databases + datasets + charts + dashboard).

Everything is derived from compact Python definitions so the whole executive dashboard
is version-controlled and reproducible — no hand-clicking in the UI. UUIDs are
deterministic (uuid5 of a fixed namespace + name) so re-imports update in place rather
than duplicating.

Output: dist/olist_bundle.zip  (Superset "Dashboard" export format).

Run inside the Superset image (it only needs PyYAML, which ships with Superset):
    python /app/bootstrap/build_bundle.py
"""
from __future__ import annotations

import os
import uuid
import zipfile
from pathlib import Path

import yaml

NS = uuid.UUID("0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9")  # fixed namespace → stable uuids


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def chart_id(name: str) -> int:
    # Deterministic positive 31-bit int id for the dashboard position chartId field.
    return int(uuid.uuid5(NS, "chartid:" + name).int % 2_000_000_000) + 1


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SQL_DIR = ROOT / "sql"
DIST = ROOT / "dist"

PROJECT = os.environ.get("GCP_PROJECT", "sctp-team2-project2-elt")
GOLD = os.environ.get("BQ_GOLD_DATASET", "olist_gold_mart_prod")

DB_NAME = "Olist BigQuery (gold mart)"
DB_UUID = uid("database:olist_bigquery")
# ADC: google-cloud-bigquery reads GOOGLE_APPLICATION_CREDENTIALS, so no secret in the URI.
DB_URI = f"bigquery://{PROJECT}/{GOLD}"


def load_sql(name: str) -> str:
    raw = (SQL_DIR / f"{name}.sql").read_text()
    return raw.replace("{{PROJECT}}", PROJECT).replace("{{GOLD}}", GOLD)


# ───────────────────────────── column / metric helpers ───────────────────────
def col(name, dtype, is_dttm=False, verbose=None):
    return {
        "column_name": name,
        "type": dtype,
        "is_dttm": is_dttm,
        "groupby": True,
        "filterable": True,
        "verbose_name": verbose,
        "description": None,
        "expression": None,
        "python_date_format": None,
        "extra": {},
    }


def metric(name, expr, label=None, fmt=None):
    return {
        "metric_name": name,
        "verbose_name": label or name,
        "expression": expr,
        "metric_type": None,
        "d3format": fmt,
        "description": None,
        "warning_text": None,
        "extra": {},
    }


PCT = ".1%"
MONEY = ",.0f"

# ───────────────────────────────── datasets ──────────────────────────────────
DATASETS = {
    "v_orders": {
        "columns": [
            col("order_id", "STRING"), col("customer_unique_id", "STRING"),
            col("customer_state", "STRING"), col("order_status", "STRING"),
            col("purchase_ts", "TIMESTAMP", is_dttm=True),
            col("order_month", "DATE", is_dttm=True, verbose="Order month"),
            col("cohort_month", "DATE", is_dttm=True),
            col("gmv", "FLOAT"), col("freight", "FLOAT"), col("n_items", "INTEGER"),
            col("payment_type", "STRING"), col("review_score", "INTEGER"),
            col("delivery_days", "INTEGER", verbose="Delivery lead time (days)"),
            col("days_vs_estimate", "INTEGER"),
            col("order_seq", "INTEGER"), col("cust_total_orders", "INTEGER"),
            col("is_repeat_order", "BOOLEAN"), col("has_subsequent_order", "BOOLEAN"),
            col("is_delivered", "BOOLEAN"), col("is_late", "BOOLEAN"),
            col("delivery_bucket", "STRING", verbose="Delivery vs promise"),
            col("review_bucket", "STRING", verbose="Review sentiment"),
            col("months_since_first", "INTEGER"),
        ],
        "metrics": [
            metric("gmv_total", "SUM(gmv)", "GMV (R$)", MONEY),
            metric("order_count", "COUNT(DISTINCT order_id)", "Orders"),
            metric("aov", "SUM(gmv) / NULLIF(COUNT(DISTINCT order_id), 0)", "Avg order value", ",.2f"),
            metric("avg_review", "AVG(review_score)", "Avg review ★", ".2f"),
            metric("avg_lead_days", "AVG(delivery_days)", "Avg lead time (days)", ".1f"),
            metric("on_time_rate",
                   "AVG(CASE WHEN days_vs_estimate IS NULL THEN NULL WHEN days_vs_estimate <= 0 THEN 1.0 ELSE 0.0 END)",
                   "On-time rate", PCT),
            metric("late_rate",
                   "AVG(CASE WHEN days_vs_estimate IS NULL THEN NULL WHEN days_vs_estimate > 0 THEN 1.0 ELSE 0.0 END)",
                   "Late rate", PCT),
            metric("reorder_rate", "AVG(CAST(has_subsequent_order AS INT64))", "Reorder rate", PCT),
            metric("repeat_order_share", "AVG(CAST(is_repeat_order AS INT64))", "Repeat-order share", PCT),
        ],
        "main_dttm": "order_month",
    },
    "v_customers": {
        "columns": [
            col("customer_unique_id", "STRING"), col("customer_state", "STRING"),
            col("frequency", "INTEGER"), col("monetary", "FLOAT"),
            col("recency_days", "INTEGER"), col("cohort_month", "DATE", is_dttm=True),
            col("is_repeat_customer", "BOOLEAN"),
            col("orders_placed_bucket", "STRING", verbose="Orders placed"),
            col("segment", "STRING", verbose="RFM segment"),
        ],
        "metrics": [
            metric("customer_count", "COUNT(DISTINCT customer_unique_id)", "Customers"),
            metric("repeat_customer_rate", "AVG(CAST(is_repeat_customer AS INT64))",
                   "Repeat-customer rate", PCT),
            metric("total_monetary", "SUM(monetary)", "Revenue (R$)", MONEY),
        ],
        "main_dttm": "cohort_month",
    },
    "v_cohort_retention": {
        "columns": [
            col("cohort_month", "DATE", is_dttm=True, verbose="Cohort (first-order month)"),
            col("months_since", "STRING", verbose="Months since first order"),
            col("months_since_num", "INTEGER"),
            col("active_customers", "INTEGER"), col("cohort_size", "INTEGER"),
            col("retention", "FLOAT"),
        ],
        "metrics": [
            metric("avg_retention", "AVG(retention)", "Retention", PCT),
        ],
        "main_dttm": "cohort_month",
    },
    "v_category": {
        "columns": [
            col("order_month", "DATE", is_dttm=True, verbose="Order month"),
            col("customer_state", "STRING"),
            col("product_category", "STRING", verbose="Category"),
            col("gmv", "FLOAT"), col("n_items", "INTEGER"),
        ],
        "metrics": [
            metric("gmv_total", "SUM(gmv)", "GMV (R$)", MONEY),
            metric("items", "SUM(n_items)", "Items sold"),
        ],
        "main_dttm": "order_month",
    },
}


def dataset_yaml(name: str) -> dict:
    d = DATASETS[name]
    return {
        "table_name": name,
        "main_dttm_col": d["main_dttm"],
        "description": f"Virtual dataset — see sql/{name}.sql",
        "default_endpoint": None,
        "offset": 0,
        "cache_timeout": None,
        "schema": None,
        "sql": load_sql(name),
        "params": None,
        "template_params": None,
        "filter_select_enabled": True,
        "fetch_values_predicate": None,
        "extra": None,
        "normalize_columns": False,
        "always_filter_main_dttm": False,
        "uuid": uid(f"dataset:{name}"),
        "metrics": d["metrics"],
        "columns": d["columns"],
        "version": "1.0.0",
        "database_uuid": DB_UUID,
    }


# ───────────────────────────────── charts ────────────────────────────────────
# Each entry: (slug, title, dataset, viz_type, extra_form_data)
ADHOC_TIME = {"time_range": "No filter"}


def m(name):  # reference a saved metric by name
    return name


CHARTS = []


def add_chart(slug, title, dataset, viz_type, form, *, width=4, height=50, subtitle=None):
    CHARTS.append({
        "slug": slug, "title": title, "dataset": dataset, "viz_type": viz_type,
        "form": form, "width": width, "height": height, "subtitle": subtitle,
    })


def big_number(slug, title, dataset, metric_name, subtitle):
    add_chart(slug, title, dataset, "big_number_total",
              {"metric": m(metric_name), "header_font_size": 0.4,
               "subheader_font_size": 0.15, "subtitle": subtitle or ""},
              width=2, height=50, subtitle=subtitle)


# ── Tab 1 · Executive (CEO) ──
big_number("kpi_gmv", "GMV (item revenue)", "v_orders", "gmv_total", "sum of item price")
big_number("kpi_orders", "Orders", "v_orders", "order_count", "distinct orders")
big_number("kpi_aov", "Avg order value", "v_orders", "aov", "GMV / orders")
big_number("kpi_repeat", "Repeat-customer rate", "v_customers", "repeat_customer_rate", "buyers with >1 order")
big_number("kpi_ontime", "On-time delivery", "v_orders", "on_time_rate", "vs promised date")
big_number("kpi_review", "Avg review", "v_orders", "avg_review", "1–5 scale")

add_chart("gmv_new_vs_repeat", "Monthly GMV — new vs repeat customers", "v_orders",
          "echarts_area",
          {"metrics": [m("gmv_total")], "groupby": ["is_repeat_order"],
           "x_axis": "order_month", "granularity_sqla": "order_month",
           "stack": "Stack", "show_legend": True,
           "x_axis_time_format": "%b %Y"},
          width=8, height=58)

add_chart("repeat_share_trend", "Repeat-order share over time", "v_orders",
          "echarts_timeseries_line",
          {"metrics": [m("repeat_order_share")], "x_axis": "order_month",
           "granularity_sqla": "order_month", "x_axis_time_format": "%b %Y",
           "y_axis_format": PCT},
          width=4, height=58)

# ── Tab 2 · Retention (CMO) ──
add_chart("cohort_heatmap", "Cohort retention — share of cohort active N months later",
          "v_cohort_retention", "heatmap_v2",
          {"x_axis": "cohort_month", "groupby": "months_since",
           "metric": m("avg_retention"), "normalize_across": "heatmap",
           "linear_color_scheme": "blue_white_yellow", "y_axis_format": PCT,
           "xscale_interval": 1, "yscale_interval": 1},
          width=8, height=60)

add_chart("orders_per_customer", "How many orders each customer places", "v_customers",
          "dist_bar",
          {"metrics": [m("customer_count")], "groupby": ["orders_placed_bucket"],
           "row_limit": 10},
          width=4, height=60)

add_chart("rfm_segments", "Customers by RFM segment", "v_customers", "dist_bar",
          {"metrics": [m("customer_count")], "groupby": ["segment"], "row_limit": 10},
          width=6, height=52)

add_chart("reorder_by_review", "Reorder rate by review sentiment", "v_orders", "dist_bar",
          {"metrics": [m("reorder_rate")], "groupby": ["review_bucket"],
           "y_axis_format": PCT, "row_limit": 10},
          width=6, height=52)

# ── Tab 3 · Delivery & Reviews (CTO) ──
add_chart("delivery_hist", "Order volume by delivery vs promise", "v_orders", "dist_bar",
          {"metrics": [m("order_count")], "groupby": ["delivery_bucket"], "row_limit": 10},
          width=6, height=56)

add_chart("late_by_state", "Late-delivery rate by customer state", "v_orders", "dist_bar",
          {"metrics": [m("late_rate")], "groupby": ["customer_state"],
           "y_axis_format": PCT, "order_desc": True, "row_limit": 27,
           "timeseries_limit_metric": m("late_rate")},
          width=6, height=56)

add_chart("review_by_delivery", "Avg review score by delivery vs promise", "v_orders", "dist_bar",
          {"metrics": [m("avg_review")], "groupby": ["delivery_bucket"], "row_limit": 10},
          width=4, height=52)

add_chart("late_rate_trend", "Late-delivery rate over time", "v_orders",
          "echarts_timeseries_line",
          {"metrics": [m("late_rate")], "x_axis": "order_month",
           "granularity_sqla": "order_month", "x_axis_time_format": "%b %Y",
           "y_axis_format": PCT},
          width=4, height=52)

add_chart("reorder_by_delivery", "Reorder rate by delivery vs promise", "v_orders", "dist_bar",
          {"metrics": [m("reorder_rate")], "groupby": ["delivery_bucket"],
           "y_axis_format": PCT, "row_limit": 10},
          width=4, height=52)

# ── Tab 4 · Catalog ──
add_chart("top_categories", "Top product categories by GMV", "v_category", "dist_bar",
          {"metrics": [m("gmv_total")], "groupby": ["product_category"],
           "order_desc": True, "row_limit": 12, "timeseries_limit_metric": m("gmv_total")},
          width=12, height=60)


def base_form(c):
    f = {
        "datasource": f'{uid("dataset:" + c["dataset"])}__table',
        "viz_type": c["viz_type"],
        "slice_id": chart_id(c["slug"]),
        "adhoc_filters": [],
        "row_limit": 10000,
        "time_range": "No filter",
    }
    f.update(c["form"])
    return f


def query_context(c, form):
    """Minimal but valid query_context so the chart loads on the dashboard."""
    ds = {"id": chart_id(c["slug"]), "type": "table",
          "uuid": uid("dataset:" + c["dataset"])}
    # collect metrics + columns from form_data
    metrics = form.get("metrics") or ([form["metric"]] if form.get("metric") else [])
    columns = []
    for key in ("groupby", "x_axis"):
        v = form.get(key)
        if isinstance(v, list):
            columns += v
        elif v:
            columns.append(v)
    q = {
        "filters": [], "extras": {"having": "", "where": ""},
        "applied_time_extras": {}, "columns": columns, "metrics": metrics,
        "annotation_layers": [], "row_limit": form.get("row_limit", 10000),
        "series_limit": 0, "order_desc": True, "url_params": {},
        "custom_params": {}, "custom_form_data": {},
    }
    return {"datasource": {"id": ds["id"], "type": "table"},
            "force": False, "queries": [q], "form_data": form,
            "result_format": "json", "result_type": "full"}


def chart_yaml(c) -> dict:
    form = base_form(c)
    return {
        "slice_name": c["title"],
        "description": c.get("subtitle"),
        "certified_by": None, "certification_details": None,
        "viz_type": c["viz_type"],
        "params": form,
        "query_context": _json(query_context(c, form)),
        "cache_timeout": None,
        "uuid": uid("chart:" + c["slug"]),
        "version": "1.0.0",
        "dataset_uuid": uid("dataset:" + c["dataset"]),
    }


import json as _jsonmod


def _json(obj) -> str:
    return _jsonmod.dumps(obj)


# ──────────────────────────────── dashboard ──────────────────────────────────
def md_box(idx, code, height=30, width=12):
    return {"type": "MARKDOWN", "id": f"MARKDOWN-{idx}",
            "meta": {"width": width, "height": height, "code": code},
            "children": [], "parents": []}


def build_position():
    pos = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID",
                      "meta": {"text": "Olist — Why we're working harder to grow"}},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["TABS-MAIN"],
                    "parents": ["ROOT_ID"]},
    }
    tabs_children = []
    counter = {"n": 0}

    def new_id(prefix):
        counter["n"] += 1
        return f"{prefix}-{counter['n']:03d}"

    def chart_node(slug, parents):
        c = next(x for x in CHARTS if x["slug"] == slug)
        cid = new_id("CHART")
        pos[cid] = {"type": "CHART", "id": cid,
                    "meta": {"width": c["width"], "height": c["height"],
                             "chartId": chart_id(slug), "sliceName": c["title"],
                             "uuid": uid("chart:" + slug)},
                    "children": [], "parents": parents}
        return cid

    def md_node(code, parents, height=28, width=12):
        mid = new_id("MARKDOWN")
        pos[mid] = {"type": "MARKDOWN", "id": mid,
                    "meta": {"width": width, "height": height, "code": code},
                    "children": [], "parents": parents}
        return mid

    def make_tab(title, blocks):
        """blocks = list of ('chart', slug) | ('md', code) | ('row', [items])."""
        tab_id = new_id("TAB")
        pos[tab_id] = {"type": "TAB", "id": tab_id, "meta": {"text": title},
                       "children": [], "parents": ["ROOT_ID", "GRID_ID", "TABS-MAIN"]}
        for block in blocks:
            row_id = new_id("ROW")
            row_parents = ["ROOT_ID", "GRID_ID", "TABS-MAIN", tab_id]
            pos[row_id] = {"type": "ROW", "id": row_id,
                           "meta": {"background": "BACKGROUND_TRANSPARENT"},
                           "children": [], "parents": row_parents}
            child_parents = row_parents + [row_id]
            for kind, payload in block:
                if kind == "chart":
                    pos[row_id]["children"].append(chart_node(payload, child_parents))
                elif kind == "md":
                    code, h, w = payload
                    pos[row_id]["children"].append(md_node(code, child_parents, h, w))
            pos[tab_id]["children"].append(row_id)
        tabs_children.append(tab_id)

    # Tab 1 — Executive (CEO)
    make_tab("1 · Executive (CEO)", [
        [("md", ("## Working harder to grow\n\n"
                 "GMV climbs (R$13.6M over the window), but the engine is "
                 "**acquisition, not loyalty**: only **~3% of customers ever order "
                 "twice**. The repeat-customer rate is the binding constraint — before "
                 "blaming pricing or competition, look at why customers don't come back. "
                 "The next tabs trace it to the delivery experience.", 26, 12))],
        [("chart", "kpi_gmv"), ("chart", "kpi_orders"), ("chart", "kpi_aov"),
         ("chart", "kpi_repeat"), ("chart", "kpi_ontime"), ("chart", "kpi_review")],
        [("chart", "gmv_new_vs_repeat"), ("chart", "repeat_share_trend")],
        [("md", ("> **CEO read:** growth is *bought*, one new customer at a time. "
                 "A few points of repeat rate is worth more than the next marketing push.",
                 16, 12))],
    ])

    # Tab 2 — Retention (CMO)
    make_tab("2 · Retention (CMO)", [
        [("md", ("## It isn't brand stickiness\n\n"
                 "Re-engagement underperforms because the **first experience** fails, not "
                 "because the brand lacks loyalty programs. Retention collapses after the "
                 "first order, and reorder rate tracks the *review* the customer left.",
                 24, 12))],
        [("chart", "cohort_heatmap"), ("chart", "orders_per_customer")],
        [("chart", "rfm_segments"), ("chart", "reorder_by_review")],
        [("md", ("> **CMO read:** spending more on loyalty comms treats the symptom. "
                 "Customers who had a good experience already come back at a higher rate.",
                 16, 12))],
    ])

    # Tab 3 — Delivery & Reviews (CTO)
    make_tab("3 · Delivery & Reviews (CTO)", [
        [("md", ("## The leak is logistics\n\n"
                 "Late deliveries are not operational noise — they are a **revenue leak**. "
                 "Average review falls monotonically as delivery slips past the promise "
                 "date — **4.29★ on-time → 3.29★ (1-3d) → 2.11★ (4-7d) → 1.69★ (8+d)** — "
                 "and low-review customers don't reorder. Most orders land on-time; the "
                 "damage is concentrated in the late tail.", 26, 12))],
        [("chart", "delivery_hist"), ("chart", "late_by_state")],
        [("chart", "review_by_delivery"), ("chart", "late_rate_trend"),
         ("chart", "reorder_by_delivery")],
        [("md", ("> **CTO read:** the cause of the CMO's retention problem is sitting in "
                 "the delivery data. Fixing late deliveries is a retention lever, not just "
                 "a cost line.", 16, 12))],
    ])

    # Tab 4 — Catalog
    make_tab("4 · Catalog", [
        [("chart", "top_categories")],
    ])

    pos["TABS-MAIN"] = {"type": "TABS", "id": "TABS-MAIN",
                        "children": tabs_children, "parents": ["ROOT_ID", "GRID_ID"],
                        "meta": {}}
    return pos


def dashboard_yaml() -> dict:
    pos = build_position()
    # native filters: date range on order_month + customer state, scoped to all charts
    native_filters = [
        {"id": "NATIVE_FILTER-month", "name": "Order month", "filterType": "filter_time",
         "type": "NATIVE_FILTER", "targets": [{}], "defaultDataMask": {},
         "controlValues": {}, "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
         "chartsInScope": [chart_id(c["slug"]) for c in CHARTS]},
        {"id": "NATIVE_FILTER-state", "name": "Customer state", "filterType": "filter_select",
         "type": "NATIVE_FILTER",
         "targets": [{"datasetUuid": uid("dataset:v_orders"), "column": {"name": "customer_state"}}],
         "defaultDataMask": {}, "controlValues": {"multiSelect": True, "searchAllOptions": True},
         "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
         "chartsInScope": [chart_id(c["slug"]) for c in CHARTS]},
    ]
    meta = {
        "show_native_filters": True,
        "native_filter_configuration": native_filters,
        "color_scheme": "supersetColors",
        "positions": pos,
        "refresh_frequency": 0,
        "expanded_slices": {},
        "label_colors": {},
        "cross_filters_enabled": True,
        "default_filters": "{}",
        "filter_scopes": {},
        "chart_configuration": {},
    }
    return {
        "dashboard_title": "Olist — Executive Dashboard",
        "description": "Why we're working harder to grow: repeat rate is the binding "
                       "constraint, and the cause is the delivery experience.",
        "css": "", "slug": "olist-executive",
        "uuid": uid("dashboard:olist_executive"),
        "version": "1.0.0",
        "position": pos,
        "metadata": meta,
    }


def database_yaml() -> dict:
    # Superset's BigQuery engine spec authenticates from the connection's
    # encrypted_extra.credentials_info (not ambient ADC). Read the mounted SA key and
    # embed it; Superset encrypts it with SECRET_KEY on import. dist/ is git-ignored.
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/app/secrets/sa.json")
    cred = _jsonmod.loads(Path(cred_path).read_text())
    return {
        "database_name": DB_NAME,
        "sqlalchemy_uri": DB_URI,
        "cache_timeout": None,
        "expose_in_sqllab": True,
        "allow_run_async": False,
        "allow_ctas": False, "allow_cvas": False, "allow_dml": False,
        "allow_file_upload": False,
        # credentials_info populates the sqlalchemy-bigquery dialect, which Superset's
        # BigQuery engine spec reads as engine.dialect.credentials_info for catalog probes.
        "extra": {
            "allows_virtual_table_explore": True,
            "engine_params": {"credentials_info": cred},
        },
        "uuid": DB_UUID,
        "version": "1.0.0",
    }


# ──────────────────────────────── write zip ──────────────────────────────────
def main():
    DIST.mkdir(exist_ok=True)
    out = DIST / "olist_bundle.zip"
    db_slug = "olist_bigquery_gold_mart"
    metadata = {"version": "1.0.0", "type": "Dashboard",
                "timestamp": "2026-06-10T00:00:00+00:00"}

    def dump(obj):
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        root = "olist_bundle"
        z.writestr(f"{root}/metadata.yaml", dump(metadata))
        z.writestr(f"{root}/databases/{db_slug}.yaml", dump(database_yaml()))
        for name in DATASETS:
            z.writestr(f"{root}/datasets/{db_slug}/{name}.yaml", dump(dataset_yaml(name)))
        for c in CHARTS:
            z.writestr(f"{root}/charts/{c['slug']}.yaml", dump(chart_yaml(c)))
        z.writestr(f"{root}/dashboards/olist_executive.yaml", dump(dashboard_yaml()))

    print(f"wrote {out} ({len(CHARTS)} charts, {len(DATASETS)} datasets)")


if __name__ == "__main__":
    main()
