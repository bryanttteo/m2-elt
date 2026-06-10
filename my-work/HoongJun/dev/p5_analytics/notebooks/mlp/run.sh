#!/usr/bin/env bash
# Execute the ML pipeline non-interactively, end-to-end.
# This script ONLY runs the pipeline — install deps separately:
#     pip install -r requirements.txt
#
# Usage:
#   ./run.sh                                   # use config.yaml as-is
#   ./run.sh --set model.name=random_forest    # override any config key
#   ./run.sh --set target=repeat_purchase --set search.enabled=true
#   MLP_MODEL=xgboost ./run.sh                 # override via env var
set -euo pipefail

# Run from this script's directory so relative config paths resolve.
cd "$(dirname "$0")"

# Use the same interpreter the user develops with unless PYTHON is overridden.
PYTHON="${PYTHON:-python}"

echo "▶ Running MLP pipeline with: $PYTHON -m src.pipeline $*"
exec "$PYTHON" -m src.pipeline "$@"
