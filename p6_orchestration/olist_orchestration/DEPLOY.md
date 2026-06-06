# Deploying the Olist ELT pipeline

The pipeline is a single Dagster code location (`olist_orchestration`) that:

1. **bronze** — loads `datasets/*.csv` into BigQuery `olist_bronze[_dev]`
   (`BRONZE_LOAD_METHOD=manual`, default) or runs Meltano (`=meltano`).
2. **stage** — dbt views in `olist_stage[_dev]` (1:1 dedup of bronze).
3. **gold_mart** — dbt tables in `olist_gold_mart[_dev]` (star schema: `fact_orders`
   + `dim_customers` / `dim_sellers` / `dim_products` / `dim_reviews`).

Jobs: `olist_full_refresh` (everything), `stg_only`, `gold_mart_only`.

## Local

```bash
cp .env.example .env.dev        # then fill in (already done for this repo)
make install                    # pip install the Dagster project
make dev                        # Dagster UI on http://localhost:3000
# or run a layer directly:
make dbt-build ENV=dev
make meltano-run
```

## Prod — Cloud Run jobs (cron-triggered)

> Assumed target: **Cloud Run jobs**. Swap for Composer/GKE if the team prefers;
> only the deploy commands below change, not the image.

The service-account keyfile is **never baked into the image** — it is mounted at
runtime from Secret Manager.

```bash
PROJECT=sctp-team2-project2-elt
REGION=asia-southeast1            # Cloud Run region (compute); BQ stays in US
REPO=olist-elt
IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/olist-elt:latest

# 1) Store the SA key in Secret Manager (one-time)
gcloud secrets create olist-sa-key --data-file=secrets/sctp-team2-project2-elt-1853e88c8665.json

# 2) Build & push (build context = repo root)
gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION
docker build -f p6_orchestration/olist_orchestration/Dockerfile -t $IMAGE .
docker push $IMAGE

# 3) Create the job — mount the secret as a file, point the env var at it
gcloud run jobs create olist-full-refresh \
  --image=$IMAGE \
  --region=$REGION \
  --set-env-vars=OLIST_ENV=prod,GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json \
  --set-secrets=/secrets/sa.json=olist-sa-key:latest \
  --task-timeout=3600 --max-retries=1 --memory=2Gi

# 4) Schedule it via Cloud Scheduler (e.g. daily 02:00 SGT)
gcloud scheduler jobs create http olist-nightly \
  --schedule="0 2 * * *" --time-zone="Asia/Singapore" \
  --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/olist-full-refresh:run" \
  --http-method=POST --oauth-service-account-email=SCHEDULER_SA@$PROJECT.iam.gserviceaccount.com
```

The container's default `CMD` runs `dagster job execute -j olist_full_refresh` and
exits — exactly the one-shot semantics Cloud Run jobs expect. For an always-on UI,
deploy the same image as a Cloud Run **service** overriding the command with
`dagster dev -h 0.0.0.0 -p 3000`.
