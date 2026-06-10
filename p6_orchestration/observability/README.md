# Olist ELT — Ops Portal

A single page showing every app, instance, and DB with **server-side health
status** and links to Grafana / Cloud Monitoring. Companion to
[`observability-plan.md`](./observability-plan.md).

## Files

| File | Purpose |
|------|---------|
| `index.html` | The portal UI. Polls `/api/status` every 15s. |
| `app.py` | Flask backend: serves the page + `/api/status` health API. |
| `Dockerfile` / `Makefile` | Container build + Cloud Run deploy (`olist-ops-portal`). |
| `requirements.txt` | Flask, gunicorn, google-auth. |
| `../../.github/workflows/deploy-ops-portal.yml` | CI deploy on push to main. |

## Status logic

Each target resolves server-side (no browser CORS) to:

- 🟢 **green** — reachable & ready (HTTP 2xx/3xx; `401` counts as alive for the
  basic-auth Dagster endpoint; a `RUNNING` VM that answers).
- 🔴 **red** — not pingable.
- 🟡 **yellow** — deployment/startup in progress: a Cloud Run service with a
  created-but-not-yet-ready revision, or a VM in `PROVISIONING/STAGING/REPAIRING`.
- ⚪ **gray** — URL not configured yet.

Green/red work with **zero GCP permissions** (plain HTTP ping). Yellow
(deploy/VM detection) needs the runtime service account to read the admin APIs;
without it the portal degrades to ping-only and shows a banner.

## Configure

Two kinds of values:

1. **Link URLs** in `index.html` — the `REPLACE_*` hrefs (what the buttons open).
2. **Health-check URLs** via env vars on the service — `DASH_URL`,
   `STREAMLIT_URL`, `WORDCLOUD_URL`, `SUPERSET_URL`, `DAGSTER_URL`. Set these as GitHub repo
   **Variables** so the deploy workflow injects them, or pass to `make deploy`.

Get the Cloud Run URLs:

```bash
gcloud run services list --region us-central1 \
  --format='value(metadata.name, status.url)'
```

## Run locally

```bash
make venv
make run DASH_URL=https://... STREAMLIT_URL=https://... \
         SUPERSET_URL=https://... DAGSTER_URL=https://...
# open http://localhost:8080
```

## Deploy

```bash
make deploy DASH_URL=... STREAMLIT_URL=... SUPERSET_URL=... DAGSTER_URL=...
```

Grant the Cloud Run runtime service account read-only access so yellow works:

```bash
SA=$(gcloud run services describe olist-ops-portal --region us-central1 \
      --format='value(spec.template.spec.serviceAccountName)')
gcloud projects add-iam-policy-binding sctp-team2-project2-elt \
  --member="serviceAccount:$SA" --role=roles/run.viewer
gcloud projects add-iam-policy-binding sctp-team2-project2-elt \
  --member="serviceAccount:$SA" --role=roles/compute.viewer
```

## Notes

- The Dagster VM is **deleted nightly**; overnight it shows red (or yellow while
  the morning recreate is `PROVISIONING`). That's expected — see the plan.
- This portal is a convenience board, **not** the alerting system. Cloud
  Monitoring uptime checks + alert policies (plan §Tier 1) remain the source of
  truth that actually pages people.
