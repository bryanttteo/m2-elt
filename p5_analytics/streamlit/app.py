"""Olist Gold Mart — Executive Dashboard (Streamlit + seaborn/matplotlib/plotly).

A narrated management deck over the ``olist_gold_mart_prod`` BigQuery gold mart
(1 fact + 5 dims). Five sections trace one story: GMV grows but the engine is paid
acquisition, not loyalty — and a late-delivery → bad-review → no-reorder chain is the
cheapest lever on it.

Run locally:   ENV=prod streamlit run app.py          (offline snapshot by default)
Live BQ:       DASH_OFFLINE=0 ENV=prod streamlit run app.py
Snapshot:      python app.py --snapshot               (rebuild parquet from BigQuery)
Serve (prod):  streamlit run app.py --server.port $PORT --server.address 0.0.0.0
"""
from __future__ import annotations

import sys

# --snapshot: rebuild the parquet cache from BigQuery and exit (used by `make snapshot`).
if "--snapshot" in sys.argv:
    import bq
    import config
    import queries

    print(f"Building snapshot from {config.GCP_PROJECT}.{config.GOLD_DATASET} ...")
    bq.refresh_all(queries.QUERIES)
    sys.exit(0)

import pandas as pd
import streamlit as st

import charts as Ch
import metrics as M

st.set_page_config(page_title="Olist · Executive Dashboard", page_icon="📦",
                   layout="wide", initial_sidebar_state="expanded")

Ch.apply_theme()


# ---------------------------------------------------------------- styling ----
st.markdown(
    """
    <style>
      .stApp { background-color: #0a0f1e; }
      .block-container { padding-top: 2rem; max-width: 1500px; }
      [data-testid="stSidebar"] { background-color: #121a2e; }
      [data-testid="stMetricValue"] { font-size: 1.9rem; }
      h1, h2, h3 { color: #e8edf7; }
      .callout { border-left: 6px solid #fb6a85; background: #121a2e;
                 padding: 16px 20px; border-radius: 8px; margin: 8px 0 4px; }
      .callout.good { border-left-color: #34d399; }
      .callout.accent { border-left-color: #4f8cff; }
      .callout h4 { color: #e8edf7; margin: 0 0 4px; font-size: 1.05rem; }
      .callout p { color: #8b9bb4; margin: 0; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------- data ----
@st.cache_data(show_spinner="Loading gold mart …")
def load_data():
    d = M.get_data()
    return d["orders"], d["category"]


def callout(headline: str, body: str, tone: str = "alert"):
    cls = {"alert": "", "good": " good", "accent": " accent"}.get(tone, "")
    st.markdown(f'<div class="callout{cls}"><h4>{headline}</h4><p>{body}</p></div>',
                unsafe_allow_html=True)


def fmt_money(x, short=True):
    if pd.isna(x):
        return "—"
    if short and abs(x) >= 1e6:
        return f"R${x/1e6:.1f}M"
    if short and abs(x) >= 1e3:
        return f"R${x/1e3:.0f}K"
    return f"R${x:,.0f}"


orders, category = load_data()
_min, _max = M.month_bounds()


# --------------------------------------------------------------- sidebar -----
st.sidebar.title("📦 Olist Gold Mart")
st.sidebar.caption("Executive dashboard · `olist_gold_mart_prod`")

section = st.sidebar.radio(
    "Section",
    ["Executive overview (CEO)", "Retention & customers (CMO)",
     "Delivery & experience (CTO)", "Product catalog", "The diagnosis"],
)

st.sidebar.divider()
months = pd.period_range(_min, _max, freq="M").to_timestamp()
date_range = st.sidebar.select_slider(
    "Purchase month range",
    options=list(months),
    value=(months[0], months[-1]),
    format_func=lambda d: d.strftime("%b %Y"),
)
all_states = M.states()
sel_states = st.sidebar.multiselect("Customer states (blank = all)", all_states, default=[])

st.sidebar.divider()
st.sidebar.caption("Marketing / CAC figures in the overview are illustrative finance "
                   "assumptions, not warehouse data.")

start, end = date_range
of = M.apply_filters(orders, start, end, sel_states or None)
full = orders  # retention/cohort logic always uses full history


# ------------------------------------------------------------------ header ---
st.title("Olist — Why we're working harder to grow")
st.caption("One connected story for the CEO, CMO and CTO · "
           f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
           + (f" · {', '.join(sel_states)}" if sel_states else " · all states"))


# =========================================================== OVERVIEW ========
if section.startswith("Executive"):
    k = M.kpis(of)
    callout("Working harder to grow: GMV climbs, but the engine is acquisition, not loyalty.",
            "The repeat-customer rate is the binding constraint. Before blaming pricing or "
            "competition, look at why customers don't come back — the next sections trace it to "
            "delivery experience.", "alert")

    c = st.columns(6)
    c[0].metric("GMV (item revenue)", fmt_money(k["gmv"]))
    c[1].metric("Orders", f"{k['orders']:,}")
    c[2].metric("Avg order value", fmt_money(k["aov"], short=False))
    c[3].metric("Repeat-customer rate", f"{k['repeat_rate']*100:.1f}%")
    c[4].metric("On-time delivery", "—" if pd.isna(k["on_time_rate"]) else f"{k['on_time_rate']*100:.0f}%")
    c[5].metric("Avg review", f"{k['avg_review']:.2f} ★")

    st.pyplot(Ch.gmv_area(M.gmv_monthly(of)), use_container_width=True)

    st.subheader("The CEO question: are we buying growth?")
    st.caption("Marketing spend, CAC and margin are not in the warehouse. Enter finance's "
               "numbers to overlay unit economics on the observed GMV / repeat behaviour.")
    sc = st.columns(3)
    spend = sc[0].number_input("Marketing spend / month (R$)", value=500_000, step=50_000)
    cac = sc[1].number_input("Target CAC (R$ / customer)", value=60, step=5)
    uplift = sc[2].number_input("Repeat-rate uplift (pp)", value=5, step=1, min_value=0, max_value=50)

    kk = dict(k, _n_months=of["order_month"].nunique())
    s = M.cac_scenario(kk, spend, cac, uplift)
    r = st.columns(4)
    r[0].metric("Blended CAC", fmt_money(s["blended_cac"], short=False))
    r[1].metric("% GMV on marketing", "—" if pd.isna(s["pct_gmv_on_marketing"]) else f"{s['pct_gmv_on_marketing']*100:.1f}%")
    r[2].metric(f"GMV upside of +{int(uplift)}pp repeat", fmt_money(s["incremental_gmv"]))
    r[3].metric("Equivalent paid-acq cost", fmt_money(s["equiv_paid_cost"]))
    st.caption(f"Lifting repeat rate by {int(uplift)}pp adds ~{fmt_money(s['incremental_gmv'])} GMV "
               f"for free — versus ~{fmt_money(s['equiv_paid_cost'])} to buy the same volume "
               f"through paid acquisition. Retention is the cheaper growth lever.")


# =========================================================== RETENTION =======
elif section.startswith("Retention"):
    opc = M.orders_per_customer(of)
    one_done = opc.loc[opc["orders_placed"] == 1, "customers"].sum() / max(opc["customers"].sum(), 1)
    callout("It isn't that the brand isn't sticky — almost nobody gets a second chance to like it.",
            f"{one_done*100:.0f}% of customers order exactly once. Cohort retention collapses to "
            "near-zero after month 0. Spending more on loyalty comms won't fix a first-purchase "
            "experience problem.", "alert")

    a, b = st.columns(2)
    with a:
        st.pyplot(Ch.repeat_share_trend(M.repeat_rate_monthly(of)), use_container_width=True)
    with b:
        st.pyplot(Ch.orders_per_customer_bar(opc), use_container_width=True)

    cohort = M.cohort_matrix(full)
    c, d = st.columns([3, 2])
    with c:
        if not cohort.empty:
            st.pyplot(Ch.cohort_heatmap(cohort), use_container_width=True)
    with d:
        st.pyplot(Ch.rfm_bar(M.rfm(full)), use_container_width=True)


# =========================================================== DELIVERY ========
elif section.startswith("Delivery"):
    callout("Late delivery is not logistics noise — it is a revenue leak that craters reviews.",
            "Review scores fall sharply the moment delivery slips past the promised date, and that "
            "score is the strongest predictor of whether a customer ever comes back.", "alert")

    a, b = st.columns(2)
    with a:
        st.pyplot(Ch.review_by_delivery_bar(M.review_by_delivery_bucket(of)), use_container_width=True)
    with b:
        st.plotly_chart(Ch.late_rate_choropleth(M.ontime_by_state(of)), use_container_width=True)

    c, d = st.columns(2)
    with c:
        st.pyplot(Ch.leadtime_hist(M.delivery_distribution(of)), use_container_width=True)
    with d:
        st.pyplot(Ch.review_dist_bar(M.review_distribution(of)), use_container_width=True)


# =========================================================== CATALOG =========
elif section.startswith("Product"):
    callout("Revenue is concentrated in a handful of categories and the southeast.",
            "The catalog and geography both follow a power law — useful for prioritising "
            "merchandising and the delivery fix where the GMV actually is.", "accent")

    tc = M.top_categories(category, start, end, sel_states or None, n=12)
    a, b = st.columns(2)
    with a:
        st.pyplot(Ch.top_categories_bar(tc), use_container_width=True)
    with b:
        # Top categories × top states GMV heatmap.
        d = category
        d = d[(d["order_month"] >= pd.to_datetime(start)) & (d["order_month"] <= pd.to_datetime(end))]
        if sel_states:
            d = d[d["customer_state"].isin(sel_states)]
        top_cats = tc["product_category"].head(10).tolist()
        top_states = (d.groupby("customer_state")["gmv"].sum().sort_values(ascending=False)
                      .head(10).index.tolist())
        piv = (d[d["product_category"].isin(top_cats) & d["customer_state"].isin(top_states)]
               .pivot_table(index="product_category", columns="customer_state",
                            values="gmv", aggfunc="sum", fill_value=0)
               .reindex(index=top_cats, columns=top_states))
        st.pyplot(Ch.category_state_heatmap(piv), use_container_width=True)


# =========================================================== DIAGNOSIS =======
elif section.startswith("The diagnosis"):
    by_rev = M.reorder_by_review_bucket(full)
    by_dlv = M.reorder_by_delivery_bucket(full)
    dlv_gap = (1 - by_dlv["reorder_rate"].iloc[-1] / by_dlv["reorder_rate"].iloc[0]) if len(by_dlv) >= 2 else 0
    rev_gap = (by_rev["reorder_rate"].iloc[-1] / by_rev["reorder_rate"].iloc[0] - 1) if len(by_rev) >= 2 else 0

    callout("One problem, three symptoms — and delivery sits upstream of all three.",
            f"Late-delivery customers reorder ~{dlv_gap*100:.0f}% less often and promoters reorder "
            f"~{rev_gap*100:.0f}% more than detractors. Repeat is already just ~3%, so the business "
            "refills almost its entire customer base every month. The CTO's 'logistics noise' is the "
            "CMO's churn is the CEO's margin — and delivery is the cheapest lever on it.", "good")

    st.pyplot(Ch.review_delivery_corr(of), use_container_width=True)

    a, b, c = st.columns(3)
    with a:
        st.pyplot(Ch.reorder_by_bucket_bar(by_dlv, "delivery_bucket",
                  "Re-order rate by delivery outcome", [Ch.GOOD, Ch.WARN, Ch.ALERT, Ch.ALERT]),
                  use_container_width=True)
    with b:
        st.pyplot(Ch.reorder_by_bucket_bar(by_rev, "review_bucket",
                  "Re-order rate by review score", [Ch.ALERT, Ch.WARN, Ch.GOOD]),
                  use_container_width=True)
    with c:
        st.pyplot(Ch.acquisition_treadmill(M.acquisition_treadmill(of)), use_container_width=True)

    st.subheader("What each leader should actually do")
    rc = st.columns(3)
    rc[0].markdown("**CEO** — Stop reading soft margin as a pricing/competition problem. Fund the "
                   "delivery fix and set a board KPI on repeat rate — the cheapest growth lever you have.")
    rc[1].markdown("**CMO** — Redirect loyalty-comms budget toward post-purchase experience and "
                   "proactive late-delivery recovery. Re-engagement can't outrun a bad first delivery.")
    rc[2].markdown("**CTO** — Treat late deliveries as lost revenue, not ops cost. Prioritise the "
                   "states and lanes with the worst late-rate; each point of on-time gain lifts retention.")


st.divider()
st.caption("Source: BigQuery `olist_gold_mart_prod` · marketing/CAC figures are illustrative "
           "assumptions, not warehouse data.")
