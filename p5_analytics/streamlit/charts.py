"""Chart factory for the Olist Streamlit dashboard.

A management deck reads best when every chart carries its own conclusion, so the
matplotlib/seaborn figures here are styled to a single dark "data-story" theme and
annotated in-place. Geographic views use Plotly (interactive choropleth); everything
statistical (distributions, bars, heatmaps, correlation) uses matplotlib + seaborn.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: never try to open a GUI window on the server.
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ---- dark palette (shared with the rest of the deck) -------------------------
CANVAS = "#0a0f1e"
SURFACE = "#121a2e"
INK = "#e8edf7"
MUTED = "#8b9bb4"
GRID = "#243049"

ACCENT = "#4f8cff"   # brand blue
ACCENT_2 = "#b794ff"  # violet — repeat / loyal
GOOD = "#34d399"     # green — on-time / promoter
WARN = "#fbbf24"     # amber — passive / caution
ALERT = "#fb6a85"    # red/pink — late / churn / detractor

FONT = ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"]


def apply_theme() -> None:
    """Register the dark matplotlib/seaborn theme once at app start."""
    sns.set_theme(style="darkgrid")
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "axes.titlecolor": INK,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.family": FONT,
        "font.size": 11,
        "legend.frameon": False,
        "figure.autolayout": True,
    })


def _new(figsize=(7, 4)):
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax


def _money_fmt(ax, axis="y"):
    def f(x, _):
        if abs(x) >= 1e6:
            return f"R${x/1e6:.1f}M"
        if abs(x) >= 1e3:
            return f"R${x/1e3:.0f}K"
        return f"R${x:.0f}"
    getattr(ax, f"{axis}axis").set_major_formatter(mticker.FuncFormatter(f))


def _pct_fmt(ax, axis="y"):
    getattr(ax, f"{axis}axis").set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))


# ============================================================== OVERVIEW =====
def gmv_area(gm: pd.DataFrame):
    fig, ax = _new((11, 4.2))
    x = gm["order_month"]
    ax.stackplot(x, gm["new_gmv"], gm["repeat_gmv"],
                 labels=["New-customer GMV", "Repeat-customer GMV"],
                 colors=[ACCENT, ACCENT_2], alpha=0.85)
    repeat_share = gm["repeat_gmv"].sum() / max(gm["total_gmv"].sum(), 1)
    ax.set_title("Monthly GMV — new vs. repeat customers")
    _money_fmt(ax)
    ax.legend(loc="upper left", labelcolor=INK)
    ax.annotate(f"Only {repeat_share*100:.0f}% of GMV is repeat business —\n"
                f"growth is almost entirely bought, one new customer at a time.",
                xy=(0.03, 0.78), xycoords="axes fraction", color=INK, fontsize=10,
                bbox=dict(boxstyle="round,pad=0.5", fc="#3a1420", ec=ALERT, lw=1))
    return fig


# ============================================================= RETENTION =====
def repeat_share_trend(rr: pd.DataFrame):
    fig, ax = _new((7, 4))
    ax.plot(rr["order_month"], rr["repeat_order_share"], color=ACCENT_2, lw=2.5, marker="o", ms=4)
    ax.axhline(rr["repeat_order_share"].mean(), color=MUTED, ls=":", lw=1)
    ax.set_title("Share of monthly orders from returning customers")
    _pct_fmt(ax)
    return fig


def orders_per_customer_bar(opc: pd.DataFrame):
    fig, ax = _new((7, 4))
    colors = [ALERT] + [ACCENT] * (len(opc) - 1)
    ax.bar(opc["label"], opc["customers"], color=colors)
    one_done = opc.loc[opc["orders_placed"] == 1, "customers"].sum() / max(opc["customers"].sum(), 1)
    ax.set_title("Customers by number of orders placed")
    ax.set_xlabel("orders placed")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K" if v >= 1000 else f"{v:.0f}"))
    ax.annotate(f"{one_done*100:.0f}% buy once and never return",
                xy=(0, opc["customers"].iloc[0]), xytext=(0.4, 0.85),
                textcoords="axes fraction", color=ALERT, fontsize=10, fontweight="bold")
    return fig


def cohort_heatmap(cohort: pd.DataFrame):
    cols = [c for c in cohort.columns if c <= 11]
    cm = cohort[cols]
    fig, ax = _new((9, 6))
    sns.heatmap(cm, ax=ax, cmap="mako", vmin=0,
                vmax=max(0.06, float(cm.iloc[:, 1:].max().max() or 0.06)),
                cbar_kws={"label": "retained", "format": mticker.PercentFormatter(xmax=1, decimals=0)},
                yticklabels=[d.strftime("%Y-%m") for d in cm.index],
                xticklabels=[f"+{c}" for c in cm.columns], linewidths=0.5, linecolor=SURFACE)
    ax.set_title("Cohort retention — % of a month's new buyers active later")
    ax.set_xlabel("months since first order")
    ax.set_ylabel("first-order cohort")
    return fig


def rfm_bar(rfm: pd.DataFrame):
    fig, ax = _new((7, 6))
    ax.barh(rfm["segment"], rfm["customers"], color=ACCENT)
    for y, (n, share) in enumerate(zip(rfm["customers"], rfm["share"])):
        ax.text(n, y, f"  {share*100:.0f}%", va="center", color=INK, fontsize=10)
    ax.invert_yaxis()
    ax.set_title("Customer segments (RFM)")
    ax.set_xlabel("customers")
    return fig


# ============================================================== DELIVERY =====
def leadtime_hist(lead: pd.Series):
    fig, ax = _new((7, 4))
    sns.histplot(lead, bins=40, color=ACCENT, ax=ax, edgecolor="none")
    if len(lead):
        ax.axvline(lead.median(), color=INK, ls=":", lw=1.5)
        ax.text(lead.median(), ax.get_ylim()[1] * 0.9, f" median {lead.median():.0f}d",
                color=INK, fontsize=10)
    ax.set_title("Delivery lead time (purchase → delivered)")
    ax.set_xlabel("days")
    ax.set_ylabel("orders")
    return fig


def review_dist_bar(rev: pd.DataFrame):
    fig, ax = _new((7, 4))
    pal = [ALERT, ALERT, WARN, GOOD, GOOD]
    scores = rev["review_score"].astype(int)
    ax.bar(scores.astype(str), rev["orders"], color=[pal[s - 1] for s in scores])
    ax.set_title("Review-score distribution")
    ax.set_xlabel("review score (★)")
    ax.set_ylabel("orders")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K" if v >= 1000 else f"{v:.0f}"))
    return fig


def review_by_delivery_bar(g: pd.DataFrame):
    fig, ax = _new((7, 4))
    pal = [GOOD, WARN, ALERT, ALERT][:len(g)]
    ax.bar(g["delivery_bucket"], g["avg_review"], color=pal)
    for i, v in enumerate(g["avg_review"]):
        ax.text(i, v + 0.08, f"{v:.2f}★", ha="center", color=INK, fontsize=10)
    if len(g) >= 2:
        drop = g["avg_review"].iloc[0] - g["avg_review"].iloc[-1]
        ax.annotate(f"Late delivery drops\nthe review by {drop:.1f}★",
                    xy=(0.97, 0.9), xycoords="axes fraction", ha="right", color=ALERT,
                    fontsize=10, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.4", fc="#3a1420", ec=ALERT, lw=1))
    ax.set_ylim(0, 5.5)
    ax.set_title("Average review score by delivery outcome")
    ax.set_ylabel("avg review (★)")
    ax.tick_params(axis="x", labelrotation=15)
    return fig


def late_rate_choropleth(by_state: pd.DataFrame):
    """Interactive Brazil choropleth (Plotly) — geo is far easier than in matplotlib."""
    import plotly.graph_objects as go

    geo = json.loads((Path(__file__).resolve().parent / "assets" / "brazil_states.geojson").read_text())
    fig = go.Figure(go.Choropleth(
        geojson=geo, locations=by_state["customer_state"], z=by_state["late_rate"],
        featureidkey="properties.sigla", colorscale="Reds", zmin=0,
        marker_line_color="white", marker_line_width=0.4,
        colorbar=dict(title="late %", tickformat=".0%"),
        hovertemplate="%{location}<br>late %{z:.1%}<extra></extra>"))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(title="Late-delivery rate by state", paper_bgcolor=SURFACE,
                      font=dict(color=INK), margin=dict(l=0, r=0, t=50, b=0), height=520)
    return fig


# =============================================================== CATALOG =====
def top_categories_bar(tc: pd.DataFrame):
    fig, ax = _new((9, 6))
    d = tc.sort_values("gmv")
    ax.barh(d["product_category"], d["gmv"], color=ACCENT)
    ax.set_title("Top product categories by GMV")
    _money_fmt(ax, "x")
    return fig


def category_state_heatmap(piv: pd.DataFrame):
    fig, ax = _new((10, 6))
    sns.heatmap(piv, ax=ax, cmap="mako", cbar_kws={"label": "GMV (R$)"},
                linewidths=0.4, linecolor=SURFACE)
    ax.set_title("Category GMV by customer state (top categories × top states)")
    ax.set_xlabel("customer state")
    ax.set_ylabel("")
    return fig


# ============================================================== DIAGNOSIS =====
def reorder_by_bucket_bar(g: pd.DataFrame, bucket_col: str, title: str, palette):
    fig, ax = _new((7, 4))
    ax.bar(g[bucket_col], g["reorder_rate"], color=palette[:len(g)])
    for i, v in enumerate(g["reorder_rate"]):
        ax.text(i, v, f" {v*100:.1f}%", ha="center", va="bottom", color=INK, fontsize=10)
    ax.set_title(title)
    _pct_fmt(ax)
    ax.set_ylabel("customers who order again")
    ax.tick_params(axis="x", labelrotation=15)
    return fig


def acquisition_treadmill(tread: pd.DataFrame):
    fig, ax = _new((9, 4.5))
    x = tread["order_month"]
    ax.bar(x, tread["new"], width=20, color=ACCENT, label="New customers")
    ax.bar(x, tread["repeat"], width=20, bottom=tread["new"], color=ACCENT_2,
           label="Returning customers")
    ax.set_title("Customers acquired each month — new vs returning")
    ax.legend(loc="upper left", labelcolor=INK)
    ax.annotate("The treadmill: the violet sliver is all the\nretention there is — "
                "the rest is re-bought each month.",
                xy=(0.03, 0.78), xycoords="axes fraction", color=INK, fontsize=10,
                bbox=dict(boxstyle="round,pad=0.5", fc="#16243f", ec=ACCENT, lw=1))
    return fig


def review_delivery_corr(of: pd.DataFrame):
    """Seaborn regression of review score on lateness — the core correlation."""
    d = of.dropna(subset=["days_vs_estimate", "review_score"]).copy()
    d = d[d["days_vs_estimate"].between(-30, 30)]
    grp = (d.groupby("days_vs_estimate")["review_score"].mean().reset_index())
    fig, ax = _new((9, 4.5))
    sns.regplot(data=grp, x="days_vs_estimate", y="review_score", ax=ax, order=2,
                scatter_kws=dict(s=18, color=ACCENT, alpha=0.7),
                line_kws=dict(color=ALERT, lw=2))
    ax.axvline(0, color=MUTED, ls=":", lw=1)
    ax.set_title("Average review score vs. days late (−early / +late)")
    ax.set_xlabel("days vs. promised date")
    ax.set_ylabel("avg review (★)")
    return fig
