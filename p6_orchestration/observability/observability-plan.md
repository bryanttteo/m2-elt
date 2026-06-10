# Observability Plan — Olist ELT Platform (Team 2)

**Status:** Proposal · **Owner:** Team 2 · **Last updated:** 2026-06-10

This plan covers monitoring, alerting, and dashboards for the full production
stack so that **engineers can debug fast** and the **manager gets a single
"is everything green?" view** without reading logs.

---

## 1. What we are observing

| # | Component | GCP type | Endpoint / ID | Notes |
|---|-----------|----------|---------------|-------|
| 1 | **Cloud SQL Postgres** (`sctp-m2-olist`) | Cloud SQL | `34.121.52.84:5432` | OLTP source + Superset metadata DB |
| 2 | **Dash** (`olist-dash`) | Cloud Run | service URL `:8080` | Live BigQuery dashboard |
| 3 | **Streamlit** (`olist-streamlit`) | Cloud Run | service URL `:8080` | Offline parquet by default |
| 3b | **Wordcloud** (`olist-wordcloud`) | Cloud Run | service URL `:8080` | Review text analysis (live BigQuery `dim_reviews`) |
| 4 | **Superset** (`olist-superset`) | Cloud Run | service URL `:8080`, min 1 instance | BI on gold mart |
| 5 | **Dagster** (`olist-dagster`) | Compute Engine VM + nginx | `:3000` (basic auth `team2`) | **Deleted nightly, recreated ~06:00** |
| 6 | **dbt docs** | served by nginx on Dagster VM | `:3000/dbt-docs/` | Same lifecycle as #5 |
| 7 | **BigQuery** (`olist_bronze/stage/gold_mart_prod`) | BigQuery (US) | — | Warehouse + cost driver |
| 8 | **ELT pipeline** (`olist_nightly` @ 02:00 SGT) | Dagster job | `olist_full_refresh` | Meltano → dbt → tests |

All in GCP project **`sctp-team2-project2-elt`**, region **us-central1**.

### Why a plain uptime check is not enough here

Two facts shape the whole design:

1. **The Dagster VM is intentionally destroyed every night** (cost saving,
   ~$40/mo). A naive uptime check would page the team every single night. We
   must treat Dagster availability as *scheduled*, not 24/7.
2. **The real product is the data, not just the web apps.** A Cloud Run service
   can be perfectly "up" (HTTP 200) while serving stale or wrong numbers because
   last night's pipeline failed. So we need **data/pipeline observability**, not
   only infrastructure uptime.

---

## 2. Design principles

- **GCP-native first.** Cloud Monitoring + Cloud Logging already collect Cloud
  Run, Cloud SQL, and BigQuery metrics for free with zero agents. Use them as
  the source of truth.
- **One pane of glass for the manager.** A single Grafana dashboard (or Cloud
  Monitoring dashboard) with traffic-light tiles. No log diving required.
- **Alert on symptoms, not noise.** Page on user-facing failure (app down,
  pipeline failed, data stale), warn on leading indicators (error rate, cost,
  latency).
- **Respect the nightly VM lifecycle.** Encode the maintenance window so Dagster
  downtime is expected, and instead verify it *comes back* each morning.
- **Cheap.** Stay within GCP free monitoring quota + Grafana Cloud free tier.

---

## 3. Tiered architecture

```
                         ┌─────────────────────────────────────────┐
                         │            GRAFANA (manager view)        │
                         │   single dashboard · traffic-light tiles │
                         └───────────────▲─────────────────────────┘
                                         │ (Cloud Monitoring datasource +
                                         │  BigQuery datasource)
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                 │                                │
┌───────▼────────┐              ┌─────────▼─────────┐            ┌─────────▼─────────┐
│ Tier 0:        │              │ Tier 1:           │            │ Tier 2:           │
│ GCP-native     │              │ Uptime + Alerting │            │ Data / pipeline   │
│ metrics+logs   │              │ (Monitoring)      │            │ observability     │
│                │              │                   │            │                   │
│ Cloud Run      │              │ Uptime checks on  │            │ Dagster run status│
│ Cloud SQL      │              │ Dash/Streamlit/   │            │ dbt test results  │
│ BigQuery       │              │ Superset URLs     │            │ BQ freshness check│
│ (auto)         │              │ + alert policies  │            │ Row-count anomaly │
└────────────────┘              └───────────────────┘            └───────────────────┘
```

### Tier 0 — GCP-native metrics & logs (foundation, ~0 effort)

Already emitted automatically; we just need to surface them.

- **Cloud Run** (Dash/Streamlit/Superset): request count, 5xx error rate, p50/p95
  latency, instance count, CPU/memory utilization, container restarts.
- **Cloud SQL**: CPU, memory, disk usage %, active connections, replication lag
  (n/a single instance), **connection refusals** (important — the nightly VM gets
  a *new IP* and must be re-added to authorized networks).
- **BigQuery**: bytes scanned per day, slot usage, query error count, **per-job
  cost** via `INFORMATION_SCHEMA.JOBS`.
- **Logs**: route all Cloud Run + VM logs to Cloud Logging (default). Add a
  log-based metric for the strings `ERROR`, `meltano ... failed`, `dbt ... FAIL`.

**Action items**
- Create log-based metric `pipeline_errors` filtering Dagster container logs for
  failures.
- Enable Cloud SQL Query Insights (free) for slow-query visibility.

### Tier 1 — Uptime checks + alerting (Cloud Monitoring)

**Uptime checks** (HTTPS, every 5 min, multi-region):

| Target | Check | Expected |
|--------|-------|----------|
| Dash URL | HTTP 200 on `/` | 24/7 |
| Streamlit URL | HTTP 200 on `/_stcore/health` | 24/7 |
| Superset URL | HTTP 200 on `/health` | 24/7 |
| Dagster `:3000` | HTTP 401/200 (basic-auth → 401 is "alive") | **business hours only** |

**Alert policies → notification channel** (start with email + a shared Slack/
Telegram webhook; manager on email only):

| Alert | Condition | Severity | Routes to |
|-------|-----------|----------|-----------|
| App down | Uptime check fails 2× consecutive (10 min) | **P1 page** | Eng + Manager |
| App 5xx spike | Cloud Run 5xx rate > 5% for 5 min | P2 | Eng |
| App latency | p95 > 5s for 10 min | P3 warn | Eng |
| Cloud SQL down / conn refused | up=0 or refusals > 0 | **P1 page** | Eng |
| Cloud SQL disk | disk util > 85% | P2 | Eng |
| BigQuery cost | bytes scanned > 50 GB/day | P2 budget | Eng + Manager |
| Pipeline failed | `pipeline_errors` metric > 0 | **P1 page** | Eng |

**Dagster nightly lifecycle handling**
- Put a **maintenance window / snooze** on the Dagster uptime alert covering the
  nightly-down period (~22:00–06:30).
- Add a **"morning recovery" check**: a Cloud Monitoring alert that fires if the
  Dagster uptime check is **still failing after 07:00** — this catches the real
  failure mode (VM didn't come back / IP not re-authorized / nginx auth not
  re-added per the runbook in `notes/setup.prod.md §11`).

### Tier 2 — Data & pipeline observability (the part that matters most)

Infra-up ≠ data-correct. Track the pipeline itself:

1. **Dagster run outcome.** The `olist_nightly` job already runs at 02:00 SGT.
   Surface its last-run status. Two options:
   - **Simplest:** Dagster supports run-failure sensors / hooks → send a webhook
     to the same Slack/Telegram channel on `olist_full_refresh` failure or
     success. Implement in `definitions.py` as a `@run_failure_sensor`.
   - **Cross-check:** because the VM may be down when an alert is read, also push
     the final job status to a BigQuery table `ops.pipeline_runs` (run_id, status,
     started, ended, rows). This survives the nightly teardown and is queryable by
     Grafana.

2. **Data freshness SLA.** Add a scheduled query / Cloud Function (runs ~04:00,
   after pipeline) checking `MAX(loaded_at)` on key gold-mart tables. Alert if the
   newest data is older than 26 hours. This is what tells the manager
   "the dashboards are showing yesterday's data."

3. **dbt test results.** The pipeline already runs dbt tests. Capture failures by
   parsing `run_results.json` (or dbt's `--store-failures`) into BigQuery, and
   count failing tests as a metric. Alert if > 0.

4. **Volume / anomaly guardrails.** Row counts of `fact_orders` and key `dim_*`
   tables per run; warn on a >20% drop vs trailing average (catches a silently
   half-loaded Meltano extract — the batch-size tuning history makes this a real
   risk).

---

## 4. Grafana — the single pane of glass

**Why Grafana on top of GCP-native:** Cloud Monitoring dashboards are fine for
engineers but clunky to share with a non-technical manager, and they can't easily
join **infra metrics + BigQuery data-quality results** on one screen. Grafana can.

**Recommended: Grafana Cloud free tier** (no infra to run, fits the
"VM-is-ephemeral" philosophy — don't put monitoring on the thing being monitored).

- **Datasource 1:** Google Cloud Monitoring (uptime, Cloud Run, Cloud SQL, BQ
  metrics) — official plugin, SA with `roles/monitoring.viewer`.
- **Datasource 2:** Google BigQuery — reads `ops.pipeline_runs`, freshness,
  dbt-test, and row-count tables for Tier 2.

**Two dashboards:**

1. **Manager / Exec ("Platform Health")** — big traffic-light stat panels:
   - 🟢/🔴 each app (Dash, Streamlit, Superset) up
   - 🟢/🔴 last night's pipeline succeeded + finish time
   - 🟢/🔴 data freshness (hours since last load)
   - dbt tests passing (X/Y)
   - BigQuery spend this month vs budget
   - Dagster status with a small "(down nightly by design)" note

2. **Engineering ("Deep Dive")** — time series:
   - Cloud Run req rate, 5xx %, p95 latency, instances per service
   - Cloud SQL CPU/connections/disk
   - BigQuery bytes scanned & cost per day, top expensive queries
   - Pipeline run duration trend, per-asset timing, row-count trend

> If we want to avoid even Grafana Cloud signup, a **Cloud Monitoring custom
> dashboard** can deliver ~80% of the manager view natively. Grafana is the
> recommended target for the joined data-quality view and nicer sharing.

---

## 5. Tooling decision & justification

| Need | Choice | Why (and what we rejected) |
|------|--------|----------------------------|
| Metrics/logs collection | **GCP Cloud Monitoring + Logging** | Already on; zero agents; covers Cloud Run + Cloud SQL + BQ natively. Rejected self-hosted Prometheus — another box to run, and Cloud Run scales to zero so a pull model is awkward. |
| Alerting | **Cloud Monitoring alert policies** | Native, integrates with uptime checks, free channels (email/Slack/PagerDuty/webhook). |
| Dashboards / manager view | **Grafana (Cloud free tier)** | Joins infra + BigQuery data quality on one screen; easy read-only share link for the manager. Cloud Monitoring dashboards as the no-signup fallback. |
| Pipeline status | **Dagster sensors + BigQuery `ops.*` tables** | Dagster already owns orchestration; sensors are the idiomatic hook. Mirroring to BigQuery makes status durable across the nightly VM teardown. |
| Data quality | **dbt tests (existing) + freshness scheduled query** | Reuse what's already running; no new framework. (Could graduate to Elementary or Great Expectations later if quality checks grow.) |
| Notifications | **Email (manager) + Slack/Telegram webhook (eng)** | Lowest friction; manager doesn't want chat noise, eng wants real-time. |

**Explicitly not adding now:** Prometheus/Loki stack, Datadog/New Relic (cost),
OpenTelemetry tracing (overkill for 3 stateless dashboards). Revisit if the
platform grows beyond these services.

---

## 6. Implementation roadmap

**Phase 1 — Foundation (½ day)**
- [ ] Uptime checks for Dash, Streamlit, Superset (24/7) + Dagster (business hrs).
- [ ] Alert policies: app down, Cloud SQL down/disk, BQ cost. Email + webhook channel.
- [ ] Snooze/maintenance window on Dagster nightly downtime + "still-down-after-07:00" alert.

**Phase 2 — Pipeline observability (1 day)**
- [ ] `@run_failure_sensor` (and success hook) in `definitions.py` → webhook.
- [ ] Write run outcomes to BigQuery `ops.pipeline_runs`.
- [ ] Freshness scheduled query (~04:00) + alert if > 26h stale.
- [ ] Capture dbt test failures → `ops.dbt_test_results`.

**Phase 3 — Dashboards (1 day)**
- [ ] Grafana Cloud project + Cloud Monitoring & BigQuery datasources (SA, viewer roles).
- [ ] Build "Platform Health" (manager) + "Deep Dive" (eng) dashboards.
- [ ] Share read-only manager dashboard link.

**Phase 4 — Polish (ongoing)**
- [ ] Row-count anomaly guardrail on `fact_orders` / `dim_*`.
- [ ] Tune alert thresholds after 1–2 weeks of baseline.
- [ ] Add SLOs (e.g. 99% app uptime in business hours; pipeline success ≥ 6/7 nights).

---

## 7. Service accounts & access (what to provision)

- `monitoring-grafana@…` — `roles/monitoring.viewer`, `roles/bigquery.dataViewer`
  + `roles/bigquery.jobUser` (for Grafana datasources).
- Reuse existing pipeline SA for writing `ops.*` tables from Dagster.
- Manager: Grafana viewer role only (no GCP console access needed).

---

## 8. Open questions for the team

1. Notification channel preference — Slack vs Telegram vs email-only?
2. Is a monthly **BigQuery budget number** agreed, so we can set the cost alert?
3. Should the Dagster VM publish a heartbeat to BigQuery on successful morning
   recreate, so "did it come back?" is a positive signal rather than absence-of-alert?
4. Grafana Cloud free tier acceptable, or must everything stay inside GCP
   (→ use Cloud Monitoring dashboards instead)?
