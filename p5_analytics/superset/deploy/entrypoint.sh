#!/usr/bin/env bash
# Cloud Run entrypoint with two modes:
#   RUN_BOOTSTRAP=1  → migrate metadata DB, ensure admin, import bundle, then EXIT
#                      (run once as a Cloud Run Job; the heavy work happens here).
#   default          → quick `db upgrade` (no-op once bootstrapped) then serve gunicorn,
#                      so the container binds $PORT well within the startup probe window.
set -euo pipefail

if [ "${RUN_BOOTSTRAP:-0}" = "1" ]; then
  echo "▶ [bootstrap] superset db upgrade"
  superset db upgrade
  echo "▶ [bootstrap] ensure admin user (${SUPERSET_ADMIN_USER})"
  superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER}" \
    --firstname "${SUPERSET_ADMIN_FIRST:-Olist}" \
    --lastname "${SUPERSET_ADMIN_LAST:-Team2}" \
    --email "${SUPERSET_ADMIN_EMAIL:-team2@olist.local}" \
    --password "${SUPERSET_ADMIN_PASSWORD}" || true
  echo "▶ [bootstrap] superset init"
  superset init
  echo "▶ [bootstrap] import asset bundle"
  superset import-dashboards --path /app/dist/olist_bundle.zip --username "${SUPERSET_ADMIN_USER}"
  echo "✓ [bootstrap] complete"
  exit 0
fi

# ── service mode ──
echo "▶ superset db upgrade (quick)"
superset db upgrade || true

echo "▶ starting gunicorn on :${PORT:-8080}"
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers "${WEB_WORKERS:-3}" \
  --timeout 120 \
  --limit-request-line 0 \
  --limit-request-field_size 0 \
  "superset.app:create_app()"
