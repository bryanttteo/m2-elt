#!/usr/bin/env bash
# Reset Dagster's local history so the UI is clean and you can re-run bronze -> stg.
# Wipes ONLY Dagster metadata (run history, event/compute logs, asset records).
# Does NOT touch BigQuery data, your code, or dbt models.
#
# Usage:
#   ./reset_dagster.sh            # reset Dagster history only
#   ./reset_dagster.sh --bronze   # ALSO drop+recreate empty bronze (clean 1x reload)
set -euo pipefail
cd "$(dirname "$0")"

# 1) stop any running `dagster dev` (it locks the SQLite history db)
if pgrep -f "dagster dev" >/dev/null 2>&1; then
  echo "Stopping running 'dagster dev'..."
  pkill -f "dagster dev" || true
  sleep 2
fi

# 2) wipe the temp Dagster instance(s) = all run/asset history
echo "Removing Dagster instance dirs (.tmp_dagster_home_*)..."
rm -rf .tmp_dagster_home_*
echo "Dagster history cleared."

# 3) (optional) reset bronze so the re-run is a clean 1x load, not an append
if [[ "${1:-}" == "--bronze" ]]; then
  PROJ=sctp-team2-project2-elt
  echo "Resetting BigQuery bronze dataset (empty, US)..."
  bq rm -r -f -d "$PROJ:olin_bronze_dev_jun"
  bq mk --location=US "$PROJ:olin_bronze_dev_jun"
  echo "Bronze reset to empty."
fi

echo
echo "Done. Next:"
echo "  dagster dev          # then materialize bronze_raw_commerce, then the dbt assets"
