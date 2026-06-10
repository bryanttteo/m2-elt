# Local setup — Superset executive dashboard

Runs the whole stack (Superset + Postgres + Redis) on your laptop via Docker, connected to
the **prod** gold mart in BigQuery (read-only).

## Prerequisites

- Docker Desktop (Compose v2).
- A GCP service-account key with **BigQuery Data Viewer + Job User** on
  `sctp-team2-project2-elt`. The repo already ships one under repo-root `./secrets/`
  (e.g. `sctp-team2-project2-elt-ROTATED-dbcb3cd092f4.json`) — the same key the rest of the
  pipeline uses.

## 1. Configure

```bash
cd m2-elt/p5_analytics/superset
cp .env.superset.example .env.superset
```

Edit `.env.superset`:

- **`SUPERSET_SECRET_KEY`** — required. Generate one: `openssl rand -base64 42`.
- `SUPERSET_ADMIN_USER` / `SUPERSET_ADMIN_PASSWORD` — your login (set to `team2`/`password`).
- `GCP_PROJECT` / `BQ_GOLD_DATASET` — default to prod; override for dev if needed.
- The SA key is mounted from repo-root `./secrets/` automatically. If your key has a
  different filename, set `SA_KEY_FILE` in `.env.superset` to its path
  (relative to this folder), e.g. `SA_KEY_FILE=../../secrets/my-key.json`.

## 2. Launch

```bash
docker compose up -d
```

This:
1. starts `db` (Postgres metadata) and `redis` (cache),
2. runs **`superset-init`** once — migrates the metadata DB, creates the admin user,
   builds the asset bundle (`dist/olist_bundle.zip`) and imports it,
3. starts the `superset` web server on **http://localhost:8088**.

Watch the bootstrap:

```bash
docker compose logs -f superset-init      # wait for "✓ bootstrap complete"
```

## 3. Verify

1. Open **http://localhost:8088**, log in.
2. **Settings → Database Connections** → *Olist BigQuery (gold mart)* → **Test connection** → OK.
3. **Datasets** → preview `v_orders` (~99k rows), `v_customers`, `v_cohort_retention`, `v_category`.
4. **Dashboards → Olist — Executive Dashboard** → all four tabs render; KPIs are non-empty.
   - Sanity vs the Dash app: repeat-customer rate ≈ **3%**, avg review ≈ **4.09★**,
     avg review by delivery bucket descends **4.29 → 3.29 → 2.10 → 1.69**.
5. Use the **Order month** and **Customer state** filters (top of the dashboard) — charts respond.

## 4. Iterate

Edit `sql/*.sql` or `bootstrap/build_bundle.py`, then re-import (idempotent — updates in place):

```bash
docker compose run --rm superset-init
```

Hard refresh the dashboard in the browser to pick up changes. To clear cached chart data,
**… (top-right) → Force refresh** on the dashboard.

## Teardown

```bash
docker compose down            # keep metadata + cache volumes
docker compose down -v         # also wipe Postgres/Redis volumes (fresh start)
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `superset-init` exits non-zero | `docker compose logs superset-init`. Usually a missing `SUPERSET_SECRET_KEY` or the SA key not mounted (check `SA_KEY_FILE`). |
| BigQuery 403 / `Access Denied` | SA lacks BigQuery Data Viewer / Job User on the project. |
| Charts show "no data" but datasets preview fine | The cached query is stale — Force refresh the dashboard, or `docker compose restart redis`. |
| Connection test fails with auth error | `GOOGLE_APPLICATION_CREDENTIALS` inside the container must point at `/app/secrets/sa.json` (default) and that file must be the mounted key. |
