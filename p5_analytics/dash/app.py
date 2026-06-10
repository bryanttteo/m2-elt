"""Olist Gold Mart — Executive Dashboard (Plotly Dash).

Run locally:   ENV=prod python app.py        (reads ../../.env.prod + secrets/)
Snapshot:      python app.py --snapshot       (bake parquet for offline/demo mode)
Serve (prod):  gunicorn app:server            (Cloud Run; DASH_OFFLINE=1 for baked image)
"""
from __future__ import annotations

import os
import sys

import dash

# dash-mantine-components 0.14+ requires React 18 (uses the useId hook). Must be set
# before the Dash app is constructed.
dash._dash_renderer._set_react_version("18.2.0")

import dash_mantine_components as dmc  # noqa: E402
from dash import Input, Output, dcc, html  # noqa: E402

import components as C
import config
import metrics as M
import views as V

# --snapshot: rebuild the parquet cache from BigQuery and exit (used by `make snapshot`).
if "--snapshot" in sys.argv:
    import bq
    import queries

    print(f"Building snapshot from {config.GCP_PROJECT}.{config.GOLD_DATASET} ...")
    bq.refresh_all(queries.QUERIES)
    sys.exit(0)

C.register_template()

app = dash.Dash(__name__, title="Olist · Executive Dashboard", suppress_callback_exceptions=True)
server = app.server  # gunicorn entrypoint

_min, _max = M.month_bounds()
_marks = {}  # date slider would need int marks; we use a DatePickerRange instead.

TABS = list(V.BUILDERS.keys())


def header():
    return dmc.Group(justify="space-between", align="center", children=[
        dmc.Stack(gap=0, children=[
            dmc.Title("Olist — Why we're working harder to grow", order=2, c=C.INK),
            dmc.Text("Gold mart · one connected story for the CEO, CMO and CTO",
                     c="dimmed", size="sm"),
        ]),
        dmc.Badge("olist_gold_mart_prod", variant="light", color="indigo", size="lg"),
    ])


def filters():
    return dmc.Paper(withBorder=True, radius="lg", p="md", shadow="sm", mb="md", children=[
        dmc.Group(align="flex-end", gap="lg", children=[
            dmc.Stack(gap=4, children=[
                dmc.Text("Purchase month range", size="xs", c="dimmed", fw=700),
                dcc.DatePickerRange(
                    id="f-dates", min_date_allowed=_min, max_date_allowed=_max,
                    start_date=_min, end_date=_max, display_format="MMM YYYY",
                ),
            ]),
            dmc.MultiSelect(
                id="f-states", label="Customer states (blank = all)",
                data=M.states(), value=[], searchable=True, clearable=True,
                style={"minWidth": 320}, maxValues=12,
            ),
        ]),
    ])


def tab_button(key):
    title, who, _ = V.BUILDERS[key]
    return dmc.TabsTab(
        dmc.Stack(gap=0, children=[dmc.Text(title, fw=700, size="sm"),
                                   dmc.Text(who, size="xs", c="dimmed")]),
        value=key)


app.layout = dmc.MantineProvider(
    forceColorScheme="dark",
    theme={"primaryColor": "indigo", "fontFamily": C.FONT,
           "defaultRadius": "md"},
    children=dmc.Container(fluid=True, px=40, py="lg", children=[
        header(),
        dmc.Space(h="md"),
        filters(),
        dmc.Tabs(id="tabs", value=os.environ.get("DEFAULT_TAB", "overview"),
                 variant="pills", color="indigo", children=[
            dmc.TabsList([tab_button(k) for k in TABS]),
        ]),
        dmc.Space(h="md"),
        dcc.Loading(html.Div(id="tab-content"), type="dot", color=C.ACCENT),
        dmc.Space(h="xl"),
        dmc.Text("Source: BigQuery olist_gold_mart_prod · marketing/CAC figures are "
                 "illustrative assumptions, not warehouse data.", size="xs", c="dimmed",
                 ta="center"),
    ]),
)


@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "value"),
    Input("f-dates", "start_date"),
    Input("f-dates", "end_date"),
    Input("f-states", "value"),
)
def render_tab(tab, start, end, sel_states):
    data = M.get_data()
    full = data["orders"]
    of = M.apply_filters(full, start, end, sel_states)
    cat = data["category"]
    k = M.kpis(of)
    _, _, builder = V.BUILDERS[tab or "overview"]
    return builder(of, full, cat, k)


@app.callback(
    Output("scenario-output", "children"),
    Input("sc-spend", "value"),
    Input("sc-cac", "value"),
    Input("sc-uplift", "value"),
    Input("f-dates", "start_date"),
    Input("f-dates", "end_date"),
    Input("f-states", "value"),
    prevent_initial_call=False,
)
def render_scenario(spend, cac, uplift, start, end, sel_states):
    of = M.apply_filters(M.get_data()["orders"], start, end, sel_states)
    return V.scenario_output(of, spend, cac, uplift)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=True)
