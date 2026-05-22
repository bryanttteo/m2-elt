"""
p1_el/webapp/app.py

Simple web app to upload CSV files into BigQuery (bronze layer).
A UI-driven companion to the dlt script — same destination (raw_commerce),
different entry point.

Auth (this build): shared service-account key, for easy cross-member local use.
  Set GOOGLE_APPLICATION_CREDENTIALS to the shared key path before running.
  The google client library reads it automatically — no key path in code.

  (Alternatives, no code change needed:
     - personal ADC:  gcloud auth application-default login  [most secure locally]
     - Cloud Run:     attach the SA at deploy with --service-account [best for prod])

Run:
  pip install flask google-cloud-bigquery pandas
  export GOOGLE_APPLICATION_CREDENTIALS=./secrets/sctp-team2-sa.json
  export GCP_PROJECT=sctp-team2-project2-elt
  export BQ_DATASET=raw_commerce
  python app.py
  # open http://localhost:8080
"""

import os
import re
import io
import sys
from flask import Flask, request, render_template, flash, redirect, url_for
from google.cloud import bigquery
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError, ServiceUnavailable, InternalServerError

# Load .env if present (convenience for shared local dev). Safe no-op if missing.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---- Config (from environment, with sensible defaults) ----
PROJECT = os.environ.get("GCP_PROJECT", "sctp-team2-project2-elt")
DATASET = os.environ.get("BQ_DATASET", "raw_commerce")
LOCATION = os.environ.get("BQ_LOCATION", "ASIA-SOUTHEAST1")
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "100"))
SA_KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")  # shared SA key path


def _check_credentials():
    """Validate auth setup at startup so misconfig fails with a clear message
    instead of a confusing error on the first request.

    A relative GOOGLE_APPLICATION_CREDENTIALS is resolved relative to THIS file's
    directory (p1_el/webapp/), so the app works no matter where you launch it from.
    """
    global SA_KEY
    if SA_KEY:
        # resolve relative paths against this file's location, not the CWD
        if not os.path.isabs(SA_KEY):
            here = os.path.dirname(os.path.abspath(__file__))
            resolved = os.path.normpath(os.path.join(here, SA_KEY))
            SA_KEY = resolved
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = resolved  # so the client sees the absolute path
        if not os.path.exists(SA_KEY):
            sys.exit(
                f"\n[AUTH ERROR] service-account key not found at:\n  {SA_KEY}\n"
                f"Fix: put the shared key at p1_el/secrets/ and set\n"
                f"  GOOGLE_APPLICATION_CREDENTIALS=../secrets/sctp-team2-project2-elt-1853e88c8665.json\n"
            )
        print(f"[auth] using shared service-account key: {SA_KEY}")
    else:
        print(
            "[auth] GOOGLE_APPLICATION_CREDENTIALS not set — falling back to ADC "
            "(gcloud auth application-default login). For shared-key mode, set the env var."
        )


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024  # reject oversized uploads

_check_credentials()

# One BigQuery client, reused. Credentials resolved automatically:
# GOOGLE_APPLICATION_CREDENTIALS (shared SA key) > attached SA > ADC.
bq = bigquery.Client(project=PROJECT, location=LOCATION)


def sanitize_table_name(name: str) -> str:
    """Make a safe BigQuery table id from a filename or user input.
    BigQuery table names: letters, numbers, underscores; can't start with a number.
    """
    base = os.path.splitext(os.path.basename(name))[0].lower()
    base = re.sub(r"[^a-z0-9_]", "_", base)      # replace illegal chars
    base = re.sub(r"_+", "_", base).strip("_")    # collapse repeats
    if not base:
        base = "uploaded_table"
    if base[0].isdigit():
        base = f"t_{base}"
    return base


def load_csv_to_bigquery(file_storage, table_name: str, write_mode: str):
    """Load an uploaded CSV (Werkzeug FileStorage) into BigQuery.
    Returns (rows_loaded, table_ref_str). Raises on failure.
    """
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"

    disposition = (
        bigquery.WriteDisposition.WRITE_TRUNCATE     # replace
        if write_mode == "replace"
        else bigquery.WriteDisposition.WRITE_APPEND   # append
    )

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,            # assume header row
        autodetect=True,                # infer schema + types (bronze = 1:1)
        write_disposition=disposition,
        allow_quoted_newlines=True,
        max_bad_records=0,              # fail loudly on bad rows for a POC
    )

    # Read the upload into a buffer and stream to BigQuery
    data = file_storage.read()

    # Retry transient 5xx errors from the resumable upload endpoint.
    # Re-wrap BytesIO each attempt because the stream is consumed on failure.
    transient_retry = retry.Retry(
        predicate=retry.if_exception_type(ServiceUnavailable, InternalServerError),
        initial=2.0, maximum=30.0, multiplier=2.0, timeout=180.0,
    )

    @transient_retry
    def _submit():
        return bq.load_table_from_file(
            io.BytesIO(data),
            table_ref,
            job_config=job_config,
        )

    load_job = _submit()
    load_job.result()  # wait for completion (raises on error)

    table = bq.get_table(table_ref)
    return table.num_rows, table_ref


@app.route("/", methods=["GET"])
def index():
    # Show existing tables in the dataset for context
    tables = []
    try:
        tables = [t.table_id for t in bq.list_tables(f"{PROJECT}.{DATASET}")]
    except GoogleAPIError:
        flash(f"Could not list tables in {DATASET}. Does the dataset exist?", "warn")
    return render_template(
        "index.html",
        project=PROJECT,
        dataset=DATASET,
        location=LOCATION,
        max_mb=MAX_MB,
        tables=sorted(tables),
        auth_mode=("shared SA key" if SA_KEY else "ADC (personal login)"),
    )


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("csv_files")
    write_mode = request.form.get("write_mode", "replace")
    custom_name = request.form.get("table_name", "").strip()

    if not files or files[0].filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    results, errors = [], []
    for f in files:
        if not f.filename.lower().endswith(".csv"):
            errors.append(f"{f.filename}: not a .csv file, skipped.")
            continue
        # If a single file and a custom name is given, use it; else derive from filename
        if custom_name and len(files) == 1:
            table_name = sanitize_table_name(custom_name)
        else:
            table_name = sanitize_table_name(f.filename)
        try:
            rows, ref = load_csv_to_bigquery(f, table_name, write_mode)
            results.append(f"{f.filename} → {ref}  ({rows:,} rows, mode={write_mode})")
        except Exception as e:  # noqa: BLE001 - surface any load error to the UI
            errors.append(f"{f.filename}: load failed — {e}")

    for r in results:
        flash(r, "success")
    for e in errors:
        flash(e, "error")
    return redirect(url_for("index"))


@app.route("/healthz")
def healthz():
    return {"status": "ok", "project": PROJECT, "dataset": DATASET}, 200


if __name__ == "__main__":
    # 0.0.0.0 so it works in a container too; Cloud Run sets PORT
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
