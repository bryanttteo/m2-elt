#!/usr/bin/env bash
# Deploy the Olist Superset dashboard to Cloud Run.
#
# Architecture:
#   • Image            — apache/superset + bigquery driver + baked asset bundle (deploy/Dockerfile.cloudrun)
#   • Metadata DB      — `superset` database on the shared Cloud SQL instance sctp-m2-olist (Postgres)
#   • Bootstrap        — a Cloud Run JOB runs the slow migrate+import once (RUN_BOOTSTRAP=1)
#   • Service          — a Cloud Run SERVICE serves gunicorn (binds fast → passes startup probe)
#   • Auth             — public (allow-unauthenticated); gated by Superset login team2 / <password>
#   • BigQuery auth    — service-account credentials embedded in the imported DB connection
#
# Prereqs: gcloud auth, the `superset` DB + user already created on sctp-m2-olist,
# and DB password in /tmp/supa_pw.txt (or edit DB_PASS below).
set -euo pipefail

PROJECT=sctp-team2-project2-elt
REGION=us-central1
CONN="${PROJECT}:${REGION}:sctp-m2-olist"
REPO="${REGION}-docker.pkg.dev/${PROJECT}/olist-elt"
TAG="${1:-v2}"
IMG="${REPO}/superset-olist:${TAG}"

DB_PASS="$(cat /tmp/supa_pw.txt)"
SECRET="$(cat /tmp/superset_secret.txt 2>/dev/null || openssl rand -base64 42 | tr -d '\n')"
ADMIN_USER="${ADMIN_USER:-team2}"
ADMIN_PW="${ADMIN_PW:-password}"

COMMON_ENV="SUPERSET_SECRET_KEY=${SECRET},DB_USER=superset,DB_PASS=${DB_PASS},DB_NAME=superset,DB_SOCKET=/cloudsql/${CONN},SUPERSET_ADMIN_USER=${ADMIN_USER},SUPERSET_ADMIN_PASSWORD=${ADMIN_PW},GCP_PROJECT=${PROJECT},BQ_GOLD_DATASET=olist_gold_mart_prod"

echo "▶ build & push image ${IMG}"
gcloud builds submit --config deploy/cloudbuild.yaml --substitutions=_IMG="$IMG" .

echo "▶ bootstrap job (migrate metadata DB + import dashboard, once)"
gcloud run jobs deploy olist-superset-bootstrap \
  --image="$IMG" --region="$REGION" --set-cloudsql-instances="$CONN" \
  --cpu=2 --memory=2Gi --max-retries=1 --task-timeout=600 \
  --set-env-vars="${COMMON_ENV},RUN_BOOTSTRAP=1"
gcloud run jobs execute olist-superset-bootstrap --region="$REGION" --wait

echo "▶ deploy service (serves gunicorn)"
gcloud run deploy olist-superset \
  --image="$IMG" --region="$REGION" --platform=managed \
  --allow-unauthenticated --add-cloudsql-instances="$CONN" \
  --min-instances=1 --max-instances=1 --cpu=2 --memory=2Gi --port=8080 \
  --timeout=300 --cpu-boost \
  --set-env-vars="$COMMON_ENV"

echo "✓ URL:"
gcloud run services describe olist-superset --region="$REGION" --format='value(status.url)'
