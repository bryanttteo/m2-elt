"""Visual system: branded **dark** Plotly template + reusable UI blocks (Mantine).

Professional dark "data-story" aesthetic — deep navy canvas, charts blend into raised
cards, vivid accents, generous margins so labels/legends never collide. Import
``register_template()`` once at app start; use the helpers everywhere.
"""
from __future__ import annotations

import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.io as pio
from dash import dcc

# ---- dark palette ------------------------------------------------------------
CANVAS = "#0a0f1e"      # page background (deep navy-black)
SURFACE = "#121a2e"     # raised cards / chart background
SURFACE_2 = "#1a2540"   # hover / inputs
INK = "#e8edf7"         # primary text (near-white)
MUTED = "#8b9bb4"       # secondary text / context series
GRID = "#243049"        # subtle gridlines / borders

ACCENT = "#4f8cff"      # primary (brand blue) — pops on dark
ACCENT_2 = "#b794ff"    # secondary (violet) — repeat / loyal
GOOD = "#34d399"        # green — on-time / promoter
WARN = "#fbbf24"        # amber — passive / caution
ALERT = "#fb6a85"       # red/pink — late / churn / detractor

# Sequential scale tuned for dark backgrounds.
SEQ_BLUE = ["#0e2748", "#16447e", "#1f6fd0", "#4f8cff", "#9cc2ff"]
SEQ_RED = ["#2a1020", "#5e1f33", "#a32f4e", "#e85575", "#ffa6b8"]

FONT = "Inter, -apple-system, Segoe UI, Roboto, sans-serif"
TEMPLATE = "olist_dark"


def register_template() -> None:
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family=FONT, size=15, color=INK),
        title=dict(font=dict(size=19, color=INK), x=0.01, xanchor="left", y=0.97, yanchor="top"),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=[ACCENT, ACCENT_2, GOOD, WARN, ALERT, MUTED],
        margin=dict(l=72, r=32, t=86, b=70),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=GRID, ticks="outside",
                   tickcolor=GRID, tickfont=dict(size=13, color=MUTED),
                   title=dict(font=dict(size=13, color=MUTED))),
        yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID,
                   tickfont=dict(size=13, color=MUTED),
                   title=dict(font=dict(size=13, color=MUTED))),
        hovermode="x unified",
        hoverlabel=dict(font_family=FONT, font_size=13, bgcolor=SURFACE_2,
                        bordercolor=GRID, font_color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right",
                    font=dict(size=13, color=MUTED), bgcolor="rgba(0,0,0,0)"),
        colorscale=dict(sequential=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)]),
    )
    pio.templates[TEMPLATE] = t
    pio.templates.default = TEMPLATE


def fig_shell(fig: go.Figure, height: int = 460) -> go.Figure:
    fig.update_layout(template=TEMPLATE, height=height, autosize=True)
    return fig


def time_axis(fig: go.Figure) -> go.Figure:
    """Thin out month ticks so 2 years of labels don't overlap."""
    fig.update_xaxes(dtick="M3", tickformat="%b %Y", tickangle=0)
    return fig


def graph(fig: go.Figure, **kwargs):
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "responsive": True},
                     style={"width": "100%"}, **kwargs)


# ---- UI blocks ---------------------------------------------------------------
def kpi_card(label: str, value: str, sub: str = "", tone: str = "ink"):
    color = {"ink": INK, "good": GOOD, "warn": WARN, "alert": ALERT, "accent": ACCENT}.get(tone, INK)
    return dmc.Paper(
        radius="lg", p="lg", className="kpi-card",
        children=[
            dmc.Text(label, size="xs", c=MUTED, tt="uppercase", fw=700,
                     style={"letterSpacing": "0.07em"}),
            dmc.Text(value, fw=800, style={"fontSize": "2.3rem", "color": color, "lineHeight": 1.1}),
            dmc.Text(sub, size="sm", c=MUTED) if sub else None,
        ],
    )


def section_title(title: str, kicker: str = ""):
    return dmc.Stack(gap=2, mb="sm", children=[
        dmc.Text(kicker, size="xs", c=ACCENT, tt="uppercase", fw=700,
                 style={"letterSpacing": "0.08em"}) if kicker else None,
        dmc.Title(title, order=3, c=INK),
    ])


def callout(headline: str, body: str, tone: str = "accent"):
    bar = {"accent": ACCENT, "alert": ALERT, "good": GOOD, "warn": WARN}.get(tone, ACCENT)
    return dmc.Paper(
        radius="md", p="lg", className="callout",
        style={"borderLeft": f"6px solid {bar}"},
        children=[
            dmc.Text(headline, fw=800, c=INK, size="xl"),
            dmc.Text(body, c=MUTED, size="sm", mt=6),
        ],
    )


def card(*children, span=12):
    return dmc.GridCol(
        dmc.Paper(radius="lg", p="md", className="chart-card", children=list(children)),
        span=span,
    )
