# p1_el/secrets/ — shared service-account key (LOCAL ONLY, NEVER COMMIT)

Holds the shared SA key used by everything in p1_el (dlt loader, webapp, meltano).

Current key: `sctp-team2-project2-elt-1853e88c8665.json`

**Gitignored. Never commit.** A leaked key lets anyone use the team's GCP billing.

## Used by
- `../webapp/app.py`  → `GOOGLE_APPLICATION_CREDENTIALS=../secrets/sctp-team2-project2-elt-1853e88c8665.json`
- `../dlt/load_olist.py` → set the same env var before running
- `../meltano/`        → target-bigquery credentials_path

## SA roles needed
- roles/bigquery.dataEditor
- roles/bigquery.jobUser
- (Iceberg/gold later) roles/bigquery.connectionAdmin + storage roles

## Rotate / revoke
```bash
# list keys
gcloud iam service-accounts keys list \
  --iam-account=sctp-team2-platform-sa@sctp-team2-project2-elt.iam.gserviceaccount.com
# delete a key id if it leaks
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=sctp-team2-platform-sa@sctp-team2-project2-elt.iam.gserviceaccount.com
```
