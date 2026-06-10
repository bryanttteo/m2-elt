# Local setup — Olist executive dashboard (Streamlit)

A narrated management deck over the `olist_gold_mart_prod` gold mart (1 fact + 5 dims),
built with **Streamlit + seaborn / matplotlib / plotly**. Shares the proven data + metrics
layer with the Dash version (`../dash/`); only the presentation layer differs.

## 1. Create the venv & install
```bash
cd p5_analytics/streamlit
make venv          # python3.11 -m venv .venv + pip install -r requirements.txt
```

## 2. Run it
By default the app runs **offline** from the baked parquet snapshot in `data/` — no
BigQuery, no credentials needed:
```bash
make run                       # → http://localhost:8501  (ENV=prod, DASH_OFFLINE=1)
```

To query **live BigQuery** instead (needs `../../.env.prod` + a key, or ADC):
```bash
DASH_OFFLINE=0 ENV=prod .venv/bin/streamlit run app.py
```

## 3. Refresh the offline snapshot from BigQuery
```bash
make snapshot      # ENV=prod DASH_OFFLINE=0 python app.py --snapshot → rewrites data/*.parquet
```
This pulls two modest result sets (`orders` ≈ 99k rows, `category`) and writes them to
`data/`. All filtering / derivation happens in pandas (see `metrics.py`), so distinct-count
metrics (repeat rate, retention) stay correct under any filter.

## 4. How it's wired
| File | Role |
|---|---|
| `config.py` | resolves project / dataset / creds from repo-root `.env.<ENV>`; `DASH_OFFLINE` toggle |
| `bq.py` | BigQuery access with a parquet cache (memo → disk → live job) |
| `queries.py` | the two SQL pulls against the gold mart |
| `metrics.py` | all pandas derivations (KPIs, cohort, RFM, reorder, treadmill) |
| `charts.py` | seaborn/matplotlib figures + the Plotly choropleth; one dark theme |
| `app.py` | Streamlit UI — sidebar filters + 5 narrated sections |
| `data/*.parquet` | baked snapshot (offline / demo source of truth) |

## 5. Container smoke test (optional, mirrors Cloud Run)
```bash
make docker-build && make docker-run      # → http://localhost:8501
```
