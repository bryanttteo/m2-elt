# Superset image with the BigQuery SQLAlchemy driver baked in.
# Pinned to a known-good Superset release for a reproducible presentation build.
FROM apache/superset:4.1.1

USER root
# BigQuery dialect + Arrow result handling. sqlalchemy-bigquery pulls in the
# google-cloud-bigquery client, which honours GOOGLE_APPLICATION_CREDENTIALS (ADC),
# so no secret needs to live in the SQLAlchemy URI.
RUN pip install --no-cache-dir \
      "psycopg2-binary==2.9.9" \
      "sqlalchemy-bigquery==1.11.0" \
      "google-cloud-bigquery==3.27.0" \
      "db-dtypes==1.3.1" \
      "pandas>=2.1"

USER superset
