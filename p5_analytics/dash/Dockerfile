# Olist executive dashboard — container image (Cloud Run / local).
#
# Two run modes (set at deploy time, no rebuild needed):
#   * Live BQ   : leave DASH_OFFLINE unset; the Cloud Run service account provides ADC.
#   * Offline   : DASH_OFFLINE=1 + bake the data/ snapshot into the image (run
#                 `make snapshot` before building) → zero BigQuery at runtime. Recommended
#                 for the live presentation: fast, reliable, no auth/cost surprises.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# App code + assets (and data/ if present — see .dockerignore to include/exclude it).
COPY . .

EXPOSE 8080

# gunicorn serves the Flask server exposed by app.py as `server`.
# Single worker keeps the in-process parquet cache warm; threads handle concurrent users.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 120 app:server
