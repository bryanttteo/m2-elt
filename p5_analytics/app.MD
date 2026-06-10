# Visualization Apps (Module 5)

Front-ends that turn the **`olist_gold_mart_prod`** gold mart into insight for the executive
presentation. Each app lives in its own folder here and consumes **gold marts only** (the
data contract) — never silver or raw.

## URLs at a glance

| App | Local | Production |
|---|---|---|
| **Dash** | http://localhost:8050 | https://olist-dash-513410438758.us-central1.run.app |
| **Superset** | http://localhost:8088 | https://olist-superset-513410438758.us-central1.run.app |
| **Streamlit** | http://localhost:8501 | https://olist-streamlit-513410438758.us-central1.run.app |

> Superset login: **team2** / **password**

---

## Status at a glance

| App | Folder | Framework | Hosting | Status | URL |
|---|---|---|---|---|---|
| **Executive Dashboard** | [`dash/`](dash/) | Plotly **Dash** + dash-mantine-components | **Cloud Run** (us-central1) | ✅ **Live** | **https://olist-dash-513410438758.us-central1.run.app** |
| **BI Dashboard** | [`superset/`](superset/) | Apache **Superset** | **Cloud Run** (us-central1) | ✅ **Live** | **https://olist-superset-513410438758.us-central1.run.app** |
| **Quick App** | [`streamlit/`](streamlit/) | **Streamlit** | **Cloud Run** (us-central1) | ✅ **Live** | **https://olist-streamlit-513410438758.us-central1.run.app** |

---

## ✅ Ready — Executive Dashboard (Plotly Dash)

**Public URL → https://olist-dash-513410438758.us-central1.run.app** (open, no login)

A presentation-grade, dark-themed dashboard that settles one management argument with data:
GMV grows but marketing spend keeps climbing because the **repeat-purchase rate (~3%) is the
binding constraint**, and the upstream cause is **delivery experience → review scores**. One
connected story across four tabs — CEO (overview), CMO (retention), CTO (delivery), and a
synthesis "diagnosis" — with per-exec recommended actions.

### Platform / framework approach
- **Framework:** Plotly **Dash** (Flask under the hood) with **dash-mantine-components** for a
  professional dark UI shell, and a custom branded Plotly template ("bold data-story" — big
  numbers, in-figure annotations that carry the conclusion).
- **Data layer:** config-driven (`config.py` reads the repo-root `.env.<env>` → project /
  dataset / creds — nothing hardcoded). Two BigQuery result sets are pulled and **cached to
  parquet** (`bq.py`); all metrics (repeat rate, cohort, RFM, CAC scenario) are derived in
  pandas (`metrics.py`); figures are built in `views.py`.
- **Hosting — Cloud Run:** deliberately **decoupled** from the Dagster pipeline VM (which is
  deleted/recreated nightly and sized with little headroom). Cloud Run is always-on, HTTPS by
  default, independently deployable, scales to zero, and ~free at this traffic.
- **Run mode — offline snapshot:** deployed as a self-contained image with the parquet **baked
  in** (`DASH_OFFLINE=1`), so the running service never touches BigQuery — fast, no auth/cost
  surprises, and immune to a gold-mart rebuild mid-presentation. (A live-BQ mode is also
  documented for always-current data.)

### Deploy / refresh
```bash
cd dash
make snapshot      # re-query BigQuery → data/*.parquet (current numbers)
make deploy        # Cloud Build image + deploy to Cloud Run (offline, public)
```
- Local run: [`dash/notes/setup.local.md`](dash/notes/setup.local.md)
- Production / Cloud Run: [`dash/notes/setup.prod.md`](dash/notes/setup.prod.md)
- Full overview: [`dash/README.md`](dash/README.md)

> Verified numbers (match BigQuery exactly): GMV ≈ **R$13.6M**, **99,441** orders,
> **3.1%** repeat rate, **93%** on-time, review **4.29★ → 1.69★** as delivery slips late.

---

## ✅ Ready — BI Dashboard (Apache Superset)

**Public URL → https://olist-superset-513410438758.us-central1.run.app**
(login-gated · **team2** / **password**)

The same executive narrative as the Dash app, rebuilt on a real BI platform so the team can
share, filter and extend it: one tabbed dashboard — **Executive (CEO)**, **Retention (CMO)**,
**Delivery & Reviews (CTO)**, **Catalog** — with native date-range + customer-state filters.
Story: **GMV grows but ~3% repeat rate is the binding constraint**, and the upstream cause is
**late delivery → low reviews → no reorder**.

### Platform / framework approach
- **Framework:** Apache **Superset** (open-source BI) querying **BigQuery directly** over
  SQLAlchemy (`sqlalchemy-bigquery`) — no extract step; charts hit the gold mart live.
- **Semantic layer:** the pandas derivations from the Dash app are translated into **SQL
  virtual datasets** (`superset/sql/`): `v_orders` (order-grain with window functions for
  sequence/cohort + delivery/review buckets), `v_customers` (RFM segments), `v_cohort_retention`,
  `v_category`. Query performance is identical to BQ views; caching is the cloud perf lever.
- **Reproducible, not hand-clicked:** the entire dashboard (datasets + 18 charts + tabbed
  layout + filters) is generated as a **version-controlled import bundle** with deterministic
  UUIDs (`superset/bootstrap/build_bundle.py`), so it rebuilds identically on any environment.
- **Hosting — Cloud Run:** image bakes the bundle; a one-time **Cloud Run Job** migrates the
  metadata DB and imports the dashboard, then the **service** serves gunicorn (binds fast →
  passes startup probe). Metadata DB = a `superset` database on the shared **Cloud SQL**
  instance `sctp-m2-olist` (persistent; survives redeploys and the nightly Dagster-VM teardown).
  Single instance, in-process cache, public ingress gated by Superset login.

### Deploy / refresh
```bash
cd superset
./deploy/deploy.sh v3          # Cloud Build image → bootstrap job (migrate+import) → deploy service
```
- Local run (Docker): [`superset/notes/setup.local.md`](superset/notes/setup.local.md)
- Production / Cloud Run: [`superset/notes/setup.prod.md`](superset/notes/setup.prod.md)
- Full overview: [`superset/README.md`](superset/README.md)

> Verified live on Cloud Run (matches BigQuery): review **4.29★ → 3.29★ → 2.11★ → 1.69★** as
> delivery slips from on-time to 8+ days late; **~3%** repeat-customer rate; GMV ≈ **R$13.6M**.

## ✅ Ready — Quick App (Streamlit)

**Public URL → https://olist-streamlit-513410438758.us-central1.run.app** (open, no login)

A lightweight Streamlit alternative for rapid one-page views ([`streamlit/`](streamlit/)).

---

> **Keep this file current.** When an app is deployed or its URL changes, update the status
> table and its section above.
