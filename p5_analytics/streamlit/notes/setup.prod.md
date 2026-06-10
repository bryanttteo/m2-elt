# Prod setup — Olist executive dashboard (Streamlit) on Cloud Run

Deploy the Streamlit dashboard as a managed container on **Cloud Run**: decoupled from the
Dagster pipeline, always-on, HTTPS by default, independently deployable, and effectively
free at presentation traffic. Reuses the project / Artifact Registry / Cloud Build from the
pipeline's prod setup.

```
Cloud Build ─▶ Artifact Registry image ─▶ Cloud Run service (HTTPS URL)
                  (bakes data/*.parquet → offline, no BigQuery at runtime)
```

## Why Cloud Run, not the Dagster VM
The pipeline VM (`olist-dagster`) is deleted nightly and recreated each morning (see
`../../notes/setup.prod.md` §11). Co-locating the dashboard there would take it down every
night and contend for RAM during a `full_refresh`. Cloud Run avoids that.

## 1. Variables (local Mac, from this folder)
```bash
export PROJECT=sctp-team2-project2-elt
export REGION=us-central1
export REPO=olist-elt                 # existing Artifact Registry repo
export SERVICE=olist-streamlit
export IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE:latest
gcloud config set project $PROJECT
```

## 2. Deploy — offline snapshot (recommended for the presentation)
The image bakes `data/*.parquet`, so the running service never touches BigQuery (no auth,
no cost, no cold-query latency, immune to a gold-mart rebuild mid-demo):
```bash
ENV=prod make snapshot                  # only if you want fresh data; data/ is already baked
make deploy                             # Cloud Build → Cloud Run, --allow-unauthenticated
# == gcloud builds submit --tag $IMAGE . ;
#    gcloud run deploy olist-streamlit --image $IMAGE --region us-central1 \
#      --allow-unauthenticated --memory 1Gi --cpu 1 --port 8080 \
#      --set-env-vars DASH_OFFLINE=1
```
Streamlit listens on `$PORT` (Cloud Run injects 8080; the Dockerfile passes it through).

## 2b. Live BigQuery mode (optional) — always current
Grant the Cloud Run runtime SA BigQuery read + job perms, then deploy with
`--set-env-vars DASH_OFFLINE=0,GCP_PROJECT=$PROJECT,BQ_LOCATION=US,BQ_GOLD_DATASET=olist_gold_mart_prod`:
```bash
PN=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
RUNTIME_SA="${PN}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUNTIME_SA" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUNTIME_SA" --role="roles/bigquery.dataViewer"
```

## 3. Access & sharing
```bash
gcloud run services describe $SERVICE --region $REGION --format='value(status.url)'
```
`--allow-unauthenticated` gives a public HTTPS URL — simplest to share for a presentation.
For private access, deploy `--no-allow-unauthenticated` and grant viewers `roles/run.invoker`.

## 4. Validation checklist
- [ ] `gcloud run services describe $SERVICE` shows the latest revision **Ready**.
- [ ] The HTTPS URL renders all five sections; overview KPIs show GMV ≈ R$13.6M, repeat ≈ 3.1%.
- [ ] (Offline) `DASH_OFFLINE=1` set and the image contains `data/*.parquet`.
- [ ] A teammate (or incognito) can load the URL.

## 5. Day-2 ops
| Task | Command |
|---|---|
| Redeploy new code | `make deploy` |
| Refresh offline snapshot | `make snapshot` → `make deploy` |
| Logs | `gcloud run services logs read $SERVICE --region $REGION` |
| Roll back | `gcloud run services update-traffic $SERVICE --region $REGION --to-revisions <REV>=100` |
| Tear down | `gcloud run services delete $SERVICE --region $REGION` |
