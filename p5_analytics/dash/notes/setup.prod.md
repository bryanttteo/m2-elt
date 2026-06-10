# Prod setup — Olist executive dashboard on Cloud Run

Deploy the Dash dashboard as a managed container on **Cloud Run**: decoupled from the
Dagster pipeline, always-on, HTTPS by default, independently deployable, and effectively
free at presentation traffic. Reuses the existing project / Artifact Registry / Cloud Build
from the pipeline's prod setup.

```
Cloud Build ─▶ Artifact Registry image ─▶ Cloud Run service (HTTPS URL) ──▶ BigQuery (US)
                                                  │
                                       runtime service account (ADC) — no keyfile in image
```

## Why Cloud Run, not the Dagster VM
The pipeline VM (`olist-dagster`, `e2-medium`) is **deleted nightly and recreated each
morning** (see `../../notes/setup.prod.md` §11) and is sized with just enough headroom
(known `exit 137` OOM risk). Co-locating the dashboard there would (a) take the dashboard
down every night and require a re-deploy + nginx re-auth each morning, (b) contend for the
4 GB during a `full_refresh`, and (c) couple a crash in one workload to the other. Cloud Run
avoids all three. A co-locate appendix is at the end if you still want it.

---

## 1. Variables (local Mac, from this folder)
```bash
export PROJECT=sctp-team2-project2-elt
export REGION=us-central1
export REPO=olist-elt                 # existing Artifact Registry repo (pipeline reuses it)
export SERVICE=olist-dash
export IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE:latest
gcloud config set project $PROJECT
```

## 2. One-time IAM — let the Cloud Run runtime SA read the gold mart
Cloud Run runs as the **Compute default service account** unless you set another. Grant it
BigQuery read + job permissions (no keyfile is shipped — the app uses ADC):
```bash
PN=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
RUNTIME_SA="${PN}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUNTIME_SA" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUNTIME_SA" --role="roles/bigquery.dataViewer"
```
> Tighter option: make a dedicated SA, grant **dataViewer on the dataset only**, and pass
> `--service-account` to `gcloud run deploy`.

Ensure required APIs are on (already enabled for the pipeline): `run`, `cloudbuild`,
`artifactregistry`, `bigquery`.

## 3. Deploy
Two modes — pick one.

### 3a. Live BigQuery (default) — always current
```bash
make deploy
# == gcloud builds submit --tag $IMAGE . ;
#    gcloud run deploy olist-dash --image $IMAGE --region us-central1 --allow-unauthenticated \
#      --memory 1Gi --cpu 1 \
#      --set-env-vars ENV=prod,GCP_PROJECT=$PROJECT,BQ_LOCATION=US,BQ_GOLD_DATASET=olist_gold_mart_prod
```
The service queries BigQuery on cold start and caches in-process. `ENV=prod` here is only a
label — Cloud Run has no `.env.prod` file, so the dataset/project come from `--set-env-vars`.

### 3b. Offline snapshot (recommended for the live presentation) — fast & self-contained
Bakes the parquet into the image so the running service never touches BigQuery (no auth,
no cost, no cold-query latency, immune to a gold-mart rebuild mid-demo):
```bash
ENV=prod make snapshot                  # writes data/*.parquet locally (needs BQ access now)
# ensure data/ is INCLUDED in the image: it is, unless you uncommented `data/` in .dockerignore
gcloud builds submit --tag $IMAGE .
gcloud run deploy $SERVICE --image $IMAGE --region $REGION --allow-unauthenticated \
  --memory 1Gi --cpu 1 --set-env-vars DASH_OFFLINE=1
```
Refresh the demo data later by re-running `make snapshot` + redeploy.

## 4. Access & sharing
```bash
gcloud run services describe $SERVICE --region $REGION --format='value(status.url)'
```
- **Open to the team:** `--allow-unauthenticated` (above) gives a public HTTPS URL — simplest
  to share for a presentation.
- **Private:** deploy with `--no-allow-unauthenticated`, then grant viewers
  `roles/run.invoker` and reach it via `gcloud run services proxy $SERVICE --region $REGION`
  (or put IAP / an LB in front).

## 5. Validation checklist
- [ ] `gcloud run services describe $SERVICE` shows the latest revision **Ready**.
- [ ] The HTTPS URL renders all four tabs; KPI cards show GMV ≈ R$13.6M, repeat ≈ 3.1%.
- [ ] (Live mode) revision logs show the two BigQuery jobs succeed on first request.
- [ ] (Offline mode) `DASH_OFFLINE=1` set and the image contains `data/*.parquet`.
- [ ] A teammate (or incognito) can load the URL.

## 6. Day-2 ops
| Task | Command |
|---|---|
| Redeploy new code | `make deploy` (or the 3b steps for offline) |
| Refresh offline snapshot | `make snapshot` → rebuild + redeploy |
| Logs | `gcloud run services logs read $SERVICE --region $REGION` |
| Roll back | `gcloud run services update-traffic $SERVICE --region $REGION --to-revisions <REV>=100` |
| Tear down | `gcloud run services delete $SERVICE --region $REGION` |

---

## Appendix — co-locating on the Dagster VM (not recommended)
If you must run it on `olist-dagster` instead of Cloud Run:
1. Build the image (§3) and `docker run -d -p 8050:8080 -e DASH_OFFLINE=1 $IMAGE` on the VM
   (offline mode so it adds ~zero BigQuery/CPU load).
2. Add an nginx `location`/server block on a new port and a basic-auth entry (mirror the
   Dagster proxy in `../../nginx-dagster.conf`).
3. **Add both steps to the nightly recreate script** (`../../notes/setup.prod.md` §11a) —
   the VM is wiped each night, so the dashboard must be re-launched + re-authed every morning.
4. Bump the machine type (e.g. `e2-medium` → `e2-standard-2`) to keep headroom for the
   pipeline's `full_refresh`, or you risk OOM (`exit 137`) killing either container.
Trade-off accepted: the dashboard's uptime is now tied to the ephemeral pipeline VM.
