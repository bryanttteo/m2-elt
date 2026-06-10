# Wordcloud app — prod deployment runbook

Streamlit "Review Text Analysis" app over BigQuery `dim_reviews`. Queries BigQuery
**live** at runtime (no offline snapshot); on Cloud Run the attached service account
provides ADC.

## Deployed (2026-06-10)

| | |
|---|---|
| Cloud Run service | `olist-wordcloud` (us-central1, project `sctp-team2-project2-elt`) |
| Live URL | https://olist-wordcloud-513410438758.us-central1.run.app |
| Image | `us-central1-docker.pkg.dev/sctp-team2-project2-elt/olist-elt/olist-wordcloud:latest` |
| Revision | `olist-wordcloud-00002-phl` (100% traffic) |
| Resources | 1Gi mem, 1 CPU, port 8080, `--allow-unauthenticated` |
| Runtime SA | `sctp-team2-project2-elt@sctp-team2-project2-elt.iam.gserviceaccount.com` (has BigQuery access) |

## Runtime BigQuery permission (important)

The app queries BigQuery live, so the Cloud Run **runtime service account** must hold
`bigquery.jobs.create` (+ data read). The default compute SA does **not** — the first
deploy failed at runtime with:

> 403 Access Denied: User does not have bigquery.jobs.create permission ...

Fix: run the service AS the pipeline SA (same identity as the ROTATED key, no key baked
into the image):

```bash
gcloud run services update olist-wordcloud --region us-central1 \
  --service-account sctp-team2-project2-elt@sctp-team2-project2-elt.iam.gserviceaccount.com
```

This is now persisted in the Makefile (`RUN_SA`, passed via `--service-account` on
`make deploy`), so future deploys keep the right identity.

## Deploy steps (what was run)

```bash
cd p5_analytics/wordcloud
make deploy                 # = the two gcloud commands below
#   1. gcloud builds submit --tag $IMAGE --project sctp-team2-project2-elt .
#   2. gcloud run deploy olist-wordcloud --image $IMAGE --region us-central1 \
#        --platform managed --allow-unauthenticated --memory 1Gi --cpu 1 --port 8080
```

Prereqs (already in place): gcloud authed (`hoongjundsai@gmail.com`), Artifact Registry
repo `olist-elt` exists, Cloud Build + Cloud Run APIs enabled. Cloud Build took ~2m53s.

Added `.dockerignore` + `.gcloudignore` so `.venv/` is not uploaded/baked (first build
uploaded 472MB before these existed).

## Verify

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://olist-wordcloud-513410438758.us-central1.run.app/_stcore/health   # 200
```

## Observability wiring (ops portal)

- `p6_orchestration/observability/index.html` — Wordcloud card "Open app" points at the
  live URL.
- Health-check env var on the running portal:
  ```bash
  gcloud run services update olist-ops-portal --region us-central1 \
    --update-env-vars WORDCLOUD_URL=https://olist-wordcloud-513410438758.us-central1.run.app
  ```
  Portal `/api/status` then reports `wordcloud -> green` (HTTP 200, running).
- For CI deploys of the portal, also set the GitHub repo **Variable** `WORDCLOUD_URL`
  to the same value (consumed by `.github/workflows/deploy-ops-portal.yml`).

## CI

`.github/workflows/deploy-wordcloud.yml` redeploys the app on push to `main` touching
`p5_analytics/wordcloud/**`.
