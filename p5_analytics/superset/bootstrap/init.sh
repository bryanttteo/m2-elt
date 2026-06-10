#!/usr/bin/env bash
# One-shot initializer: migrate metadata DB → create admin → build & import the
# asset bundle (database + datasets + charts + dashboard). Idempotent: safe to re-run.
set -euo pipefail

echo "▶ superset db upgrade"
superset db upgrade

echo "▶ create admin user (${SUPERSET_ADMIN_USER})"
superset fab create-admin \
  --username "${SUPERSET_ADMIN_USER}" \
  --firstname "${SUPERSET_ADMIN_FIRST:-Olist}" \
  --lastname "${SUPERSET_ADMIN_LAST:-Admin}" \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@olist.local}" \
  --password "${SUPERSET_ADMIN_PASSWORD}" || true

echo "▶ superset init (roles & perms)"
superset init

echo "▶ build asset bundle"
python /app/bootstrap/build_bundle.py

echo "▶ import asset bundle"
# SUPERSET_LOAD_EXAMPLES not needed; import the generated zip and overwrite on re-run.
superset import-dashboards --path /app/dist/olist_bundle.zip --username "${SUPERSET_ADMIN_USER}"

echo "✓ bootstrap complete"
