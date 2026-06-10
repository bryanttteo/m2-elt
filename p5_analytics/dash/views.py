"""Tab content builders. Each ``build_*`` takes already-filtered + full order frames and
returns a Mantine layout tree of cards holding annotated Plotly figures.

The figures are deliberately opinionated: each one carries its own conclusion via an
in-figure annotation, so the dashboard reads like a narrated deck.
"""
from __future__ import annotations

import json
from pathlib import Path

import dash_mantine_components as dmc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

import components as C
import metrics as M

_GEO = None


def _brazil_geo():
    global _GEO
    if _GEO is None:
        p = Path(__file__).resolve().parent / "assets" / "brazil_states.geojson"
        _GEO = json.loads(p.read_text())
    return _GEO


def _fmt_money(x, short=True):
    if pd.isna(x):
        return "—"
    if short:
        if abs(x) >= 1e6:
            return f"R${x/1e6:.1f}M"
        if abs(x) >= 1e3:
            return f"R${x/1e3:.0f}K"
    return f"R${x:,.0f}"


def _fmt_pct(x, d=0):
    return "—" if pd.isna(x) else f"{x*100:.{d}f}%"


def _fmt_int(x):
    return "—" if pd.isna(x) else f"{int(x):,}"


# ============================================================ OVERVIEW (CEO) ==
def build_overview(of, full, cat, k):
    kpis = M.kpis(of)
    gm = M.gmv_monthly(of)

    kpi_row = dmc.SimpleGrid(
        cols={"base": 2, "sm": 3, "lg": 6}, spacing="md",
        children=[
            C.kpi_card("GMV (item revenue)", _fmt_money(kpis["gmv"]), "sum of item price", "accent"),
            C.kpi_card("Orders", _fmt_int(kpis["orders"]), "distinct orders"),
            C.kpi_card("Avg order value", _fmt_money(kpis["aov"], short=False)),
            C.kpi_card("Repeat-customer rate", _fmt_pct(kpis["repeat_rate"], 1),
                       "buyers with >1 order", "alert"),
            C.kpi_card("On-time delivery", _fmt_pct(kpis["on_time_rate"], 0),
                       "vs promised date", "warn"),
            C.kpi_card("Avg review", f"{kpis['avg_review']:.2f} ★", "1–5 scale"),
        ],
    )

    # GMV split: new vs repeat revenue + orders line.
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gm["order_month"], y=gm["new_gmv"], name="New-customer GMV",
                             mode="lines", stackgroup="g", line=dict(width=0.5, color=C.ACCENT),
                             fillcolor="rgba(37,99,235,0.55)"))
    fig.add_trace(go.Scatter(x=gm["order_month"], y=gm["repeat_gmv"], name="Repeat-customer GMV",
                             mode="lines", stackgroup="g", line=dict(width=0.5, color=C.ACCENT_2),
                             fillcolor="rgba(124,58,237,0.55)"))
    repeat_share = gm["repeat_gmv"].sum() / max(gm["total_gmv"].sum(), 1)
    fig.add_annotation(xref="paper", yref="paper", x=0.03, y=0.80, showarrow=False,
                       align="left", xanchor="left", bgcolor="rgba(251,106,133,0.12)",
                       bordercolor=C.ALERT, borderwidth=1, borderpad=10, font=dict(color=C.INK),
                       text=f"<b>Only {repeat_share*100:.0f}% of GMV is repeat business.</b><br>"
                            f"Growth is almost entirely bought, one new customer at a time.")
    fig.update_layout(title="Monthly GMV — new vs. repeat customers", yaxis_title="GMV (R$)")
    C.time_axis(fig)
    C.fig_shell(fig, 480)

    scenario = dmc.Paper(
        withBorder=True, radius="lg", p="lg", shadow="sm",
        children=[
            C.section_title("The CEO question: are we buying growth?", "Scenario · assumption, not warehouse data"),
            dmc.Text("Marketing spend, CAC and margin are not in the data warehouse. "
                     "Enter finance's numbers to overlay unit economics on the observed GMV / "
                     "repeat behaviour.", c="dimmed", size="sm", mb="md"),
            dmc.SimpleGrid(cols={"base": 1, "sm": 3}, spacing="md", children=[
                dmc.NumberInput(id="sc-spend", label="Marketing spend / month (R$)",
                                value=500000, step=50000, thousandSeparator=","),
                dmc.NumberInput(id="sc-cac", label="Target CAC (R$ / customer)",
                                value=60, step=5),
                dmc.NumberInput(id="sc-uplift", label="Repeat-rate uplift (pp)",
                                value=5, step=1, min=0, max=50),
            ]),
            html.Div(id="scenario-output", style={"marginTop": "16px"}),
        ],
    )

    return [
        C.callout(
            "Working harder to grow: GMV climbs, but the engine is acquisition, not loyalty.",
            "The repeat-customer rate is the binding constraint. Before blaming pricing or "
            "competition, look at why customers don't come back — the next two tabs trace it to "
            "delivery experience.", "alert"),
        dmc.Space(h="md"),
        kpi_row,
        dmc.Space(h="lg"),
        dmc.Grid([C.card(C.graph(fig), span=12)]),
        dmc.Space(h="md"),
        scenario,
    ]


def scenario_output(of, spend, cac, uplift):
    k = M.kpis(of)
    k["_n_months"] = of["order_month"].nunique()
    s = M.cac_scenario(k, spend or 0, cac or 0, uplift or 0)
    cards = dmc.SimpleGrid(cols={"base": 2, "lg": 4}, spacing="md", children=[
        C.kpi_card("Blended CAC", _fmt_money(s["blended_cac"], short=False),
                   "spend ÷ customers acquired", "warn"),
        C.kpi_card("% GMV on marketing", _fmt_pct(s["pct_gmv_on_marketing"], 1),
                   "acquisition intensity", "alert"),
        C.kpi_card(f"GMV upside of +{int(uplift or 0)}pp repeat", _fmt_money(s["incremental_gmv"]),
                   f"≈ {_fmt_int(s['extra_repeat_customers'])} more repeat buyers", "good"),
        C.kpi_card("Equivalent paid-acq cost", _fmt_money(s["equiv_paid_cost"]),
                   "to buy that GMV instead", "accent"),
    ])
    return [cards, dmc.Text(
        f"Lifting repeat rate by {int(uplift or 0)}pp adds ~{_fmt_money(s['incremental_gmv'])} GMV "
        f"for free — versus ~{_fmt_money(s['equiv_paid_cost'])} to buy the same volume through "
        f"paid acquisition. Retention is the cheaper growth lever.",
        c="dimmed", size="sm", mt="sm")]


# ========================================================== RETENTION (CMO) ==
def build_retention(of, full, cat, k):
    rr = M.repeat_rate_monthly(of)
    opc = M.orders_per_customer(of)
    cohort = M.cohort_matrix(full)
    rfm = M.rfm(full)

    one_done = opc.loc[opc["orders_placed"] == 1, "customers"].sum() / max(opc["customers"].sum(), 1)

    # Repeat order share trend.
    f1 = go.Figure()
    f1.add_trace(go.Scatter(x=rr["order_month"], y=rr["repeat_order_share"], mode="lines+markers",
                            line=dict(color=C.ACCENT_2, width=3), name="Repeat order share"))
    f1.add_hline(y=rr["repeat_order_share"].mean(), line_dash="dot", line_color=C.MUTED,
                 annotation_text="average", annotation_position="top left")
    f1.update_layout(title="Share of monthly orders from returning customers",
                     yaxis_tickformat=".0%", yaxis_title="repeat order share")
    C.time_axis(f1)
    C.fig_shell(f1, 420)

    # One-and-done distribution.
    f2 = go.Figure(go.Bar(x=opc["label"], y=opc["customers"],
                          marker_color=[C.ALERT] + [C.ACCENT] * (len(opc) - 1)))
    f2.add_annotation(x=opc["label"].iloc[0], y=opc["customers"].iloc[0], yshift=14,
                      showarrow=False, font=dict(color=C.ALERT, size=13),
                      text=f"<b>{one_done*100:.0f}% buy once and never return</b>")
    f2.update_layout(title="Customers by number of orders placed", yaxis_title="customers",
                     xaxis_title="orders placed")
    C.fig_shell(f2, 420)

    # Cohort heatmap.
    if not cohort.empty:
        cols = [c for c in cohort.columns if c <= 11]
        cm = cohort[cols]
        f3 = go.Figure(go.Heatmap(
            z=cm.values, x=[f"+{c}" for c in cm.columns],
            y=[d.strftime("%Y-%m") for d in cm.index],
            colorscale=[[0, C.SURFACE], [0.15, "#16447e"], [0.5, "#1f6fd0"], [1, "#9cc2ff"]],
            zmin=0, zmax=max(0.06, float(cm.iloc[:, 1:].max().max() or 0.06)),
            xgap=2, ygap=2,
            colorbar=dict(title="retained", tickformat=".0%"),
            hovertemplate="cohort %{y}<br>month %{x}<br>%{z:.1%}<extra></extra>"))
        f3.update_layout(title="Cohort retention — % of a month's new buyers active later",
                         xaxis_title="months since first order")
        C.fig_shell(f3, 520)
    else:
        f3 = go.Figure()

    # RFM segments.
    f4 = go.Figure(go.Bar(y=rfm["segment"], x=rfm["customers"], orientation="h",
                          marker_color=C.ACCENT,
                          text=[f"{v*100:.0f}%" for v in rfm["share"]], textposition="outside"))
    f4.update_layout(title="Customer segments (RFM)", xaxis_title="customers",
                     yaxis=dict(autorange="reversed"), margin=dict(l=170))
    C.fig_shell(f4, 520)

    return [
        C.callout(
            "It isn't that the brand isn't sticky — it's that almost nobody gets a second chance to like it.",
            f"{one_done*100:.0f}% of customers order exactly once. Cohort retention collapses to "
            "near-zero after month 0. Spending more on loyalty comms won't fix a first-purchase "
            "experience problem.", "alert"),
        dmc.Space(h="md"),
        dmc.Grid([
            C.card(C.graph(f1), span=6),
            C.card(C.graph(f2), span=6),
            C.card(C.graph(f3), span=8),
            C.card(C.graph(f4), span=4),
        ]),
    ]


# =========================================================== DELIVERY (CTO) ==
def build_delivery(of, full, cat, k):
    lead = M.delivery_distribution(of)
    by_state = M.ontime_by_state(of)
    rev = M.review_distribution(of)
    rev_by_dlv = M.review_by_delivery_bucket(of)
    late_m = M.late_rate_monthly(of)

    # Lead-time histogram.
    f1 = go.Figure(go.Histogram(x=lead, nbinsx=40, marker_color=C.ACCENT))
    if len(lead):
        f1.add_vline(x=lead.median(), line_dash="dot", line_color=C.INK,
                     annotation_text=f"median {lead.median():.0f}d", annotation_position="top right")
    f1.update_layout(title="Delivery lead time (purchase → delivered)", xaxis_title="days",
                     yaxis_title="orders")
    C.fig_shell(f1, 430)

    # Late rate by state choropleth.
    f2 = go.Figure(go.Choropleth(
        geojson=_brazil_geo(), locations=by_state["customer_state"],
        z=by_state["late_rate"], featureidkey="properties.sigla",
        colorscale="Reds", zmin=0, marker_line_color="white",
        colorbar=dict(title="late %", tickformat=".0%"),
        hovertemplate="%{location}<br>late %{z:.1%}<extra></extra>"))
    f2.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    f2.update_layout(title="Late-delivery rate by state", margin=dict(l=0, r=0, t=70, b=0))
    C.fig_shell(f2, 560)

    # Review distribution.
    colors = [C.ALERT, C.ALERT, C.WARN, C.GOOD, C.GOOD]
    f3 = go.Figure(go.Bar(x=rev["review_score"].astype(int).astype(str), y=rev["orders"],
                          marker_color=[colors[int(s) - 1] for s in rev["review_score"]]))
    f3.update_layout(title="Review-score distribution", xaxis_title="review score (★)",
                     yaxis_title="orders")
    C.fig_shell(f3, 430)

    # THE killer chart: avg review by delivery bucket.
    f4 = go.Figure(go.Bar(x=rev_by_dlv["delivery_bucket"], y=rev_by_dlv["avg_review"],
                          marker_color=[C.GOOD, C.WARN, C.ALERT, C.ALERT][:len(rev_by_dlv)],
                          text=[f"{v:.2f}★" for v in rev_by_dlv["avg_review"]],
                          textposition="outside"))
    if len(rev_by_dlv) >= 2:
        drop = rev_by_dlv["avg_review"].iloc[0] - rev_by_dlv["avg_review"].iloc[-1]
        f4.add_annotation(xref="paper", yref="paper", x=0.97, y=0.92, showarrow=False,
                          align="right", xanchor="right", font=dict(color=C.ALERT, size=14),
                          bgcolor="rgba(251,106,133,0.12)", bordercolor=C.ALERT, borderpad=8,
                          text=f"<b>Late delivery drops the<br>review by {drop:.1f}★</b>")
    f4.update_layout(title="Average review score by delivery outcome", yaxis_title="avg review (★)",
                     yaxis_range=[0, 5.4])
    C.fig_shell(f4, 430)

    return [
        C.callout(
            "Late delivery is not logistics noise — it is a revenue leak that craters reviews.",
            "Review scores fall sharply the moment delivery slips past the promised date, and that "
            "score is the strongest predictor of whether a customer ever comes back (next tab).",
            "alert"),
        dmc.Space(h="md"),
        dmc.Grid([
            C.card(C.graph(f4), span=6),
            C.card(C.graph(f2), span=6),
            C.card(C.graph(f1), span=6),
            C.card(C.graph(f3), span=6),
        ]),
    ]


# ========================================================= DIAGNOSIS (ALL) ==
def _flow_figure():
    steps = [
        ("Late\ndelivery", C.ALERT),
        ("Low review\nscore", C.ALERT),
        ("Lower repeat\nprobability", C.WARN),
        ("More paid\nacquisition", C.ACCENT),
        ("Soft\nmargin", C.INK),
    ]
    fig = go.Figure()
    n = len(steps)
    for i, (label, color) in enumerate(steps):
        x0 = i * (1 / n) + 0.01
        x1 = (i + 1) * (1 / n) - 0.04
        fig.add_shape(type="rect", xref="paper", yref="paper", x0=x0, x1=x1, y0=0.25, y1=0.75,
                      line=dict(color=color, width=2), fillcolor=color, opacity=0.22)
        fig.add_annotation(xref="paper", yref="paper", x=(x0 + x1) / 2, y=0.5, showarrow=False,
                           text=f"<b>{label}</b>".replace("\n", "<br>"),
                           font=dict(color=color, size=14))
        if i < n - 1:
            fig.add_annotation(xref="paper", yref="paper", x=x1 + 0.005, y=0.5, ax=x1 + 0.03, ay=0,
                               xanchor="left", text="→", showarrow=False,
                               font=dict(size=22, color=C.MUTED))
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_layout(title="The chain the org isn't connecting", height=210,
                      margin=dict(l=10, r=10, t=56, b=10), template=C.TEMPLATE,
                      paper_bgcolor=C.SURFACE, plot_bgcolor=C.SURFACE)
    return fig


def build_diagnosis(of, full, cat, k):
    by_rev = M.reorder_by_review_bucket(full)
    by_dlv = M.reorder_by_delivery_bucket(full)
    tread = M.acquisition_treadmill(of)

    # Relative gaps (the honest way to read tiny absolute reorder rates near the 3% base).
    rev_gap = (by_rev["reorder_rate"].iloc[-1] / by_rev["reorder_rate"].iloc[0] - 1) if len(by_rev) >= 2 else 0
    dlv_gap = (1 - by_dlv["reorder_rate"].iloc[-1] / by_dlv["reorder_rate"].iloc[0]) if len(by_dlv) >= 2 else 0

    f_dlv = go.Figure(go.Bar(x=by_dlv["delivery_bucket"], y=by_dlv["reorder_rate"],
                             marker_color=[C.GOOD, C.WARN, C.ALERT, C.ALERT][:len(by_dlv)],
                             text=[f"{v*100:.1f}%" for v in by_dlv["reorder_rate"]],
                             textposition="outside"))
    f_dlv.add_annotation(xref="paper", yref="paper", x=0.98, y=0.95, showarrow=False,
                         align="right", font=dict(color=C.ALERT, size=12),
                         text=f"<b>Late buyers reorder<br>~{dlv_gap*100:.0f}% less often</b>")
    f_dlv.update_layout(title="Re-order rate by delivery outcome", yaxis_tickformat=".1%",
                        yaxis_title="customers who order again")
    C.fig_shell(f_dlv, 430)

    f_rev = go.Figure(go.Bar(x=by_rev["review_bucket"], y=by_rev["reorder_rate"],
                             marker_color=[C.ALERT, C.WARN, C.GOOD][:len(by_rev)],
                             text=[f"{v*100:.1f}%" for v in by_rev["reorder_rate"]],
                             textposition="outside"))
    f_rev.add_annotation(xref="paper", yref="paper", x=0.5, y=0.95, showarrow=False,
                         font=dict(color=C.GOOD, size=12),
                         text=f"<b>Promoters reorder ~{rev_gap*100:.0f}% more than detractors</b>")
    f_rev.update_layout(title="Re-order rate by review score", yaxis_tickformat=".1%",
                        yaxis_title="customers who order again")
    C.fig_shell(f_rev, 430)

    # The acquisition treadmill: each month is refilled almost entirely with new customers.
    f_tr = go.Figure()
    f_tr.add_trace(go.Bar(x=tread["order_month"], y=tread["new"], name="New customers",
                          marker_color=C.ACCENT))
    f_tr.add_trace(go.Bar(x=tread["order_month"], y=tread["repeat"], name="Returning customers",
                          marker_color=C.ACCENT_2))
    f_tr.add_annotation(xref="paper", yref="paper", x=0.03, y=0.80, showarrow=False, align="left",
                        xanchor="left", font=dict(color=C.INK, size=13),
                        bgcolor="rgba(79,140,255,0.12)", bordercolor=C.ACCENT, borderpad=8,
                        text="<b>The treadmill:</b> the violet sliver is all the<br>"
                             "retention there is. The rest is re-bought each month.")
    f_tr.update_layout(title="Customers acquired each month — new vs returning", barmode="stack",
                       yaxis_title="customers")
    C.time_axis(f_tr)
    C.fig_shell(f_tr, 430)

    def rec(owner, color, text):
        return C.card(dmc.Stack(gap=4, children=[
            dmc.Badge(owner, color=None, variant="filled",
                      style={"backgroundColor": color, "alignSelf": "flex-start"}),
            dmc.Text(text, size="sm", c=C.INK),
        ]), span=4)

    return [
        C.callout(
            "One problem, three symptoms — and delivery sits upstream of all three.",
            f"Late-delivery customers reorder ~{dlv_gap*100:.0f}% less often and promoters reorder "
            f"~{rev_gap*100:.0f}% more than detractors. The absolute numbers are small only because "
            "repeat is already just 3% — so the business refills almost its entire customer base "
            "every month at ~R$130 CAC (Executive overview). The CTO's 'logistics noise' is the "
            "CMO's churn is the CEO's margin, and delivery is the cheapest lever on it.", "good"),
        dmc.Space(h="md"),
        dmc.Grid([C.card(C.graph(_flow_figure()), span=12)]),
        dmc.Space(h="sm"),
        dmc.Grid([
            C.card(C.graph(f_dlv), span=4),
            C.card(C.graph(f_rev), span=4),
            C.card(C.graph(f_tr), span=4),
        ]),
        dmc.Space(h="md"),
        C.section_title("What each leader should actually do", "Recommended actions"),
        dmc.Grid([
            rec("CEO", C.ACCENT,
                "Stop reading soft margin as a pricing/competition problem. Fund the delivery fix "
                "and set a board KPI on repeat rate — it is the cheapest growth lever you have."),
            rec("CMO", C.ACCENT_2,
                "Redirect loyalty-comms budget toward post-purchase experience and proactive late-"
                "delivery recovery. Re-engagement emails can't outrun a bad first delivery."),
            rec("CTO", C.ALERT,
                "Treat late deliveries as lost revenue, not ops cost. Prioritise the states and "
                "lanes with the worst late-rate; each point of on-time gain lifts retention."),
        ]),
    ]


BUILDERS = {
    "overview": ("Executive overview", "CEO", build_overview),
    "retention": ("Retention & customers", "CMO", build_retention),
    "delivery": ("Delivery & experience", "CTO", build_delivery),
    "diagnosis": ("The diagnosis", "Synthesis", build_diagnosis),
}
