# Production setup — Superset executive dashboard

> **✅ Deployed (live).** Public URL: **https://olist-superset-513410438758.us-central1.run.app**
> (login **team2** / **password**). Running on **Cloud Run** (`olist-superset`, us-central1,
> min/max instances = 1, public ingress). Metadata DB = the `superset` database on the shared
> **Cloud SQL** instance `sctp-m2-olist` (persistent — survives redeploys and the nightly
> Dagster-VM teardown). BigQuery auth via the service-account credentials embedded in the
> imported DB connection. Reproduce/refresh with `./deploy/deploy.sh <tag>`.
>
> **Deploy mechanics:** image built from `deploy/Dockerfile.cloudrun` via
> `deploy/cloudbuild.yaml` (bakes in `dist/olist_bundle.zip`). A one-time **Cloud Run Job**
> (`olist-superset-bootstrap`, `RUN_BOOTSTRAP=1`) runs `db upgrade` + `import-dashboards`
> against Cloud SQL; the **service** then only runs a quick `db upgrade` + gunicorn so it binds
> `$PORT` fast and passes the startup probe. Caching is in-process SimpleCache (single instance).
>
> The sections below document the design rationale and the alternative (separate-VM) path.

Local is covered by [`setup.local.md`](setup.local.md). This is about **where prod runs**.

Superset is a **stateful** app: its metadata DB (dashboards, charts, users) and cache must
live on persistent infrastructure. The single hard rule:

> **The metadata Postgres must live somewhere the nightly teardown never touches.**
> Our `olist-dagster` prod VM is *deleted nightly and recreated each morning*
> (see `notes/setup.prod.md §11` in the repo root). Anything stateful co-located on it is
> wiped every night.

## ⚠️ Do NOT co-locate with the Dagster prod VM

Putting Superset on the Dagster VM looks convenient but breaks in three ways:

1. **Nightly teardown wipes it.** The VM (and any Superset metadata DB on it) is destroyed
   each night — the morning of a presentation you'd find an empty/stale Superset.
2. **Resource contention.** Superset (gunicorn web workers + Postgres + Redis) competes
   with Dagster's webserver/daemon/runs for CPU/RAM; on a small VM that means OOM kills or
   slow dashboards and slow pipeline runs.
3. **Port / nginx collisions** that must be re-applied after every nightly rebuild.

Pick one of the two isolated options below instead.

---

## Option A — Separate GCP VM + docker-compose + nginx  *(recommended; matches existing infra)*

A small Compute Engine VM dedicated to Superset, **not** on the nightly teardown schedule.
Mirrors the existing olist VM pattern (nginx basic-auth, `team2`/password).

1. **Provision** an `e2-medium` (2 vCPU / 4 GB) VM, Ubuntu, with a static IP. Grant its
   service account **BigQuery Data Viewer + Job User**, or copy the SA key to the VM.
2. **Install** Docker + compose plugin.
3. **Deploy**: clone the repo (or copy `p5_analytics/superset/` + `secrets/`), then:
   ```bash
   cp .env.superset.example .env.superset   # strong SECRET_KEY, real admin password
   docker compose up -d
   ```
   The bundled Postgres volume (`superset_db`) persists on the VM's disk — survives reboots
   and is independent of the Dagster VM.
4. **nginx** reverse-proxy in front of `localhost:8088` with HTTP basic-auth
   (`team2`/password) + TLS (Let's Encrypt), same as the dagster nginx block. Because this
   VM is not torn down nightly, the auth config is applied **once**, not re-added daily.
5. **Backups**: `docker compose exec db pg_dump -U superset superset > backup.sql` before
   the presentation, so the deck's dashboard is recoverable.

**Why recommended:** simplest operationally, isolates resources, survives the nightly
teardown, and reuses the auth/TLS pattern the team already runs.

---

## Option B — Cloud Run  *(serverless, but with real caveats)*

Cloud Run works **only** if state is externalized — its container filesystem is ephemeral
and it can run multiple instances:

1. **Metadata DB → Cloud SQL Postgres** (mandatory). SQLite/local Postgres won't survive
   Cloud Run restarts or scale-out. Point `SQLALCHEMY_DATABASE_URI` at Cloud SQL (via the
   Cloud SQL connector / private IP). This Cloud SQL instance is the persistent home that
   the nightly Dagster teardown never touches — that's the whole point.
2. **Cache → Memorystore (Redis)** over a VPC connector, or fall back to
   `CACHE_TYPE=FileSystemCache` (per-instance, lost on restart — acceptable for a short demo).
3. **`min-instances=1`** — avoids a cold start (Superset boots slowly) mid-presentation.
4. **No Celery / async** — keep `allow_run_async=False` (already set). Synchronous queries
   only; fine for a dashboard, and it sidesteps needing a separate worker + results backend.
5. **Auth to BigQuery** — attach a runtime **service account** with BigQuery Data Viewer +
   Job User (preferred; no key file), or mount the SA key via Secret Manager and set
   `GOOGLE_APPLICATION_CREDENTIALS`.
6. **Concurrency** — set container concurrency modestly (e.g. 10) and 1–2 vCPU / 2 GB.

Deploy sketch:
```bash
gcloud run deploy olist-superset \
  --image gcr.io/<proj>/olist-superset:latest \
  --min-instances 1 --cpu 2 --memory 2Gi --concurrency 10 \
  --add-cloudsql-instances <proj>:<region>:superset-meta \
  --set-secrets SUPERSET_SECRET_KEY=superset-secret:latest \
  --service-account superset-bq@<proj>.iam.gserviceaccount.com
```

**Trade-off:** more moving parts (Cloud SQL + VPC connector + Secret Manager) than Option A,
but fully decoupled from any VM and scales to zero between demos (set `min-instances=0` to
save cost when idle, accepting a cold start).

---

## Recommendation

For a one-off but **important** presentation: **Option A (separate VM)** — fewest surprises,
persistent, isolated from the nightly teardown, reuses the team's nginx/TLS pattern. Move to
Cloud Run later if you want serverless/scale-to-zero economics.

After prod is verified, take the second checkpoint commit.
