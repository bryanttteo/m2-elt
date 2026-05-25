# p1_el / webapp — CSV → BigQuery Uploader
**Module 1** · Owner: John / Bryan · A UI companion to the dlt loader.

## Purpose
A simple Flask web app to upload CSV files through a browser into the **bronze** layer (`raw_commerce`). Same destination as `../dlt/load_olist.py`, but interactive — useful for ad-hoc loads or non-CLI teammates.

## Auth: shared service-account key (for easy cross-member use)
Every member uses the **same SA key file** so no one needs personal `gcloud` setup.
The google client reads the key from `GOOGLE_APPLICATION_CREDENTIALS` automatically — **no key path in code**.

> ⚠️ A shared key is convenient but the least secure option (it sits on each laptop). Fine for this POC; the key is gitignored. For production, prefer personal ADC locally or an attached SA on Cloud Run (both need zero code change).

### One-time: get the key (one person does this, shares securely)
```bash
gcloud iam service-accounts keys create ../secrets/sctp-team2-project2-elt-1853e88c8665.json \
  --iam-account=sctp-team2-platform-sa@sctp-team2-project2-elt.iam.gserviceaccount.com
```
Share via password manager / encrypted channel — **never commit it, never email it**.
The SA needs `roles/bigquery.dataEditor` + `roles/bigquery.jobUser`.

## Needs (inputs)
- CSV file(s) to upload.
- Target dataset `raw_commerce` created in the project.
- The shared key at `p1_el/secrets/sctp-team2-project2-elt-1853e88c8665.json` (gitignored).

## Produces (outputs)
- BigQuery tables in `raw_commerce` (one per uploaded CSV), schema auto-detected.
- Row counts shown back in the UI.

## Hand-off (→ M3 dbt)
Lands bronze `raw_commerce.*` tables that silver models read from — same contract as the dlt path.

## Run locally (every member, same steps)
```bash
pip install -r requirements.txt

# option A — use a .env file (easiest for the team)
cp .env.example .env          # then ensure the key is at ../secrets/sctp-team2-project2-elt-1853e88c8665.json
python app.py

# option B — export vars manually
export GOOGLE_APPLICATION_CREDENTIALS=../secrets/sctp-team2-project2-elt-1853e88c8665.json
export GCP_PROJECT=sctp-team2-project2-elt
export BQ_DATASET=raw_commerce
python app.py

# open http://localhost:8080  (footer shows which auth mode is active)
```
The app validates the key at startup and exits with a clear message if the path is wrong.

## Config (environment variables)
| Var | Default | Meaning |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | (unset → ADC) | path to the shared SA key |
| `GCP_PROJECT` | sctp-team2-project2-elt | target project |
| `BQ_DATASET` | raw_commerce | target dataset (bronze) |
| `BQ_LOCATION` | ASIA-SOUTHEAST1 | region (must match dataset) |
| `MAX_UPLOAD_MB` | 100 | per-file size cap |
| `FLASK_SECRET` | dev-secret-change-me | set a real value if exposed |

## Files
- `app.py` — Flask app (auto-detects schema; replace/append; startup auth check).
- `templates/index.html` — upload UI (shows active auth mode + target).
- `secrets/` — the shared key goes here (gitignored).
- `.env.example` — copy to `.env` and fill.
- `Dockerfile` — for the optional Cloud Run deploy.

## Deploy to Cloud Run later (no key file — attached SA)
```bash
gcloud run deploy csv-uploader --source . --region=asia-southeast1 \
  --service-account=sctp-team2-platform-sa@sctp-team2-project2-elt.iam.gserviceaccount.com \
  --set-env-vars=GCP_PROJECT=sctp-team2-project2-elt,BQ_DATASET=raw_commerce
# the attached SA provides credentials — GOOGLE_APPLICATION_CREDENTIALS not needed
```

## Notes
- `autodetect=True` (bronze = 1:1 with source; cleaning happens in dbt silver).
- `max_bad_records=0` → fails loudly on malformed rows (good for a POC).
- For the Olist bulk load, the dlt script is faster; this app is for interactive/ad-hoc uploads + a demo-able UI.
