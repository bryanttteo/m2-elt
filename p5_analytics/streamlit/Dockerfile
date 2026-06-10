# Olist executive dashboard (Streamlit) — container image for Cloud Run / local.
#
# Two run modes (set at deploy time, no rebuild needed):
#   * Offline (default): DASH_OFFLINE=1 + the baked data/ snapshot → zero BigQuery at
#                        runtime. Recommended for the live presentation: fast & reliable.
#   * Live BQ          : DASH_OFFLINE=0; the Cloud Run service account provides ADC.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DASH_OFFLINE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# App code + the baked data/ snapshot (see .dockerignore).
COPY . .

EXPOSE 8080

# Streamlit binds to $PORT (Cloud Run injects it). Single process keeps the in-process
# parquet cache warm.
CMD exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
