# Plan 2 — Production Deploy (Meltano + dbt + Dagster on GCP)

> Goal: stand up the Olist ELT in **prod** on Google Cloud so the team gets
> **seamless reporting** — a managed Dagster UI to trigger/observe materializations,
> a nightly auto-refresh, and BigQuery/Looker Studio/dbt-docs surfaces for everyone.
>
> Companion to `plan1.md` (which covered naming + model refactor). This plan covers
> **only deployment**. It supersedes the starter notes in
> `p6_orchestration/olist_orchestration/DEPLOY.md`.
>
> **Local is unchanged.** Your day-to-day stays `make dev` / `make dbt-build ENV=dev`
> against `.env.dev`, running Python directly. Docker and the VM are **prod only** —
> they package and run the same code in the cloud.

---

## 0. Decisions locked (from review)

| Decision | Choice | Why |
|---|---|---|
| **Dagster UI host** | **Compute Engine VM** (`e2-medium`, 2 vCPU / 4 GB) running **one `dagster dev` container** (webserver + daemon bundled — same as local) | Comfortable headroom for `dagster dev` + dbt + run workers (no OOM worries); identical to local `make dev`; the bundled daemon also fires the nightly schedule — no separate Cloud Run Job needed |
| **Run-history storage** | **SQLite on a persistent Docker volume** (the local default), *not* Postgres | Matches local exactly. The only real risk (ephemeral container FS) is removed by mounting `DAGSTER_HOME` on a persistent volume. Upgrade to Postgres only if you hit SQLite locking — see §14 |
| **Prod config** | Two VM-only files at the repo root: **`.env.prod`** (non-sensitive) + **`.env.key`** (the SA keyfile) | Mirrors the local `.env.dev` + keyfile pattern. Both git-ignored; `.env.prod` is passed via `docker --env-file`, `.env.key` is mounted as the credential (by `run-dagster.sh`) |
| **Auth in prod** | **Service-account keyfile** — `.env.key` mounted to `/secrets/sa.json`, pointed to by `GOOGLE_APPLICATION_CREDENTIALS` in `.env.prod` | Same mechanism as local; `profiles.yml` `method: oauth` → `google.auth.default()` reads the keyfile |
| **Bronze source** | **Bake `datasets/` into the image**, manual CSV→BQ load (`BRONZE_LOAD_METHOD=manual`) | Static Olist dataset; simplest; no GCS round-trip |
| **Reporting surfaces** | **All four**: Dagster UI · Looker Studio on `gold_mart` · BigQuery direct access · dbt docs site | Covers engineers (Dagster/dbt-docs) and business users (Looker/BQ) |
| **Image registry / build** | **Artifact Registry** + **Cloud Build** (or local `docker build`) | Standard GCP path |

All GCP infra is in **US** (`us-central1` for the VM + Artifact Registry), colocated with the
BigQuery **`US`** multi-region data. (The nightly schedule still fires at 02:00 **Asia/Singapore**
— a team-timing choice, independent of region.)

> **Topology note:** this is deliberately the *local-style* setup (one `dagster dev` process,
> SQLite) — not Dagster's split webserver/daemon/Postgres production topology. For a single-VM
> course project with a nightly job and occasional manual runs, local-style is simpler and
> sufficient. The heavier topology is documented as an **upgrade path** in §14.
>
> **One secret to protect:** the only sensitive artifact is the SA keyfile (`.env.key`). It is
> git-ignored and lives on the VM only — never baked into the image, never committed.

---

## 1. Current-state readiness review

**Already in place (good foundation):**

- Env-driven config: `OLIST_ENV=prod` → loads `.env.prod` → datasets drop the `_dev` suffix
  (`olist_bronze`, `olist_stage`, `olist_gold_mart`). See `olist_orchestration/config.py`.
- Working `Dockerfile` installing all three tools (`dagster`, `dbt-bigquery`, `meltano`) in one image.
- dbt `profiles.yml` uses `method: oauth` → works with the mounted keyfile with **no change**.
- Pipeline assets + jobs already defined: `bronze_raw_commerce` → `dbt_models` (stage views → gold tables);
  jobs `olist_full_refresh`, `stg_only`, `gold_mart_only`.
- `dbt_project.yml` materializes `stage` as views, `gold_mart` as tables, with `+tags` for selection,
  and `store_failures: true` for data-test auditing.

**Gaps this plan fixes (Phase 0):**

| # | Gap | Fix |
|---|---|---|
| G1 | `Dockerfile` does `COPY .env.prod` but `.env.prod` is **git-ignored** → clean CI build fails | Stop baking it. Prod config comes from `.env.prod` on the VM via `docker --env-file` (§4.2, §6.2) |
| G2 | The image must not carry the keyfile | Keyfile (`.env.key`) is **mounted** at runtime to `/secrets/sa.json`; `.env.prod` sets `GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json` |
| G3 | No Dagster **schedule** defined → nothing runs automatically | Add a `ScheduleDefinition` for `olist_full_refresh` (nightly) in `definitions.py` |
| G4 | `DAGSTER_HOME` is in-container SQLite → run history lost on restart | Mount `DAGSTER_HOME` on a **persistent Docker volume** on the VM — SQLite history survives restarts (no Postgres needed at this scale) |
| G5 | Default `CMD` is one-shot `dagster job execute` (Cloud-Run-Job shaped) | `run-dagster.sh` overrides it with `dagster dev` (webserver + daemon bundled, same as local). Image default left unchanged so it can still run as a one-shot job if ever needed |
| G6 | UI has **no authentication** | Never expose `:3000` publicly — bind to localhost, reach via SSH tunnel / IAP (Phase 3) |

---

## 2. Target architecture

```
                    ┌────────────────────────────────────────────────┐
   team browser ───▶│  Compute Engine VM  (e2-medium, us-central1)    │
   (SSH tunnel /    │                                                 │
    IAP)            │   one container:                                │
                    │     dagster dev  :3000   (webserver + daemon)   │
                    │       ← Materialize / nightly schedule          │
                    │   DAGSTER_HOME → persistent volume (SQLite hist) │
                    │   config ← .env.prod (env_file, non-sensitive)  │
                    │   auth   ← .env.key  (SA keyfile → /secrets/...) │
                    │                                                 │
                    │   on each run, in-container: Meltano/load + dbt ─┼──┐
                    └────────────────────────────────────────────────┘  │
                                                                         ▼
                              ┌───────────────────────────────────────────────┐
                              │ BigQuery  (US)                                 │
                              │  olist_bronze → olist_stage → olist_gold_mart  │
                              └───────────────────────────────────────────────┘
                                   │              │                │
                       Looker Studio        BigQuery          dbt docs site
                       dashboards        direct access     (lineage / tests)
                       (business)        (analysts/BI)      (engineers)
```

One image, **one** long-running container. Meltano + dbt are **CLI tools Dagster shells out to
inside the run** — they are *not* separately hosted.

---

## 3. Prerequisites (one-time)

```bash
# Run all commands from the repo root (where run-dagster.sh, cloudbuild.yaml, .env.*, datasets/ live).
REPO_ROOT=/Users/cheonghoongjun/Documents/dev/github-dev/sctp-dsai-forked/dsai-m2-elt/m2-elt
cd "$REPO_ROOT"

PROJECT=sctp-team2-project2-elt
REGION=us-central1
ZONE=us-central1-a
REPO=olist-elt
gcloud config set project $PROJECT

# Enable the APIs we use
gcloud services enable \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  iap.googleapis.com
```

### 3.1 Service account & keyfile

Reuse the **existing project service account** — the same one whose keyfile you use locally
(`secrets/sctp-team2-project2-elt-*.json`). That keyfile becomes `.env.key` on the VM (Phase 2).

```bash
SA_EMAIL=sctp-team2-project2-elt@$PROJECT.iam.gserviceaccount.com

# BigQuery (idempotent — it already has these from local use):
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" --role="roles/bigquery.dataEditor"

# Artifact Registry read — so the VM (running as this SA) can pull the image:
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" --role="roles/artifactregistry.reader"

# Cloud Build runs as the DEFAULT COMPUTE service account; grant it the builder role
# or `gcloud builds submit` 403s on storage.objects.get for the source bucket:
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

> Two roles of this one SA: it's **attached to the VM** (so `docker pull` from Artifact
> Registry authenticates), and its **keyfile** (`.env.key`) authenticates BigQuery inside the
> container. `dataEditor` at project level is simplest for a course; tighten to per-dataset later.

---

## 4. Phase 0 — Repo changes (do these first, commit on a branch)

Only two small repo edits are needed; everything else is cloud-side. (Both done in this repo.)

### 4.1 Add the nightly schedule (G3)

In `p6_orchestration/olist_orchestration/olist_orchestration/definitions.py`:

```python
from dagster import ScheduleDefinition, DefaultScheduleStatus  # add to imports

olist_nightly = ScheduleDefinition(
    name="olist_nightly",
    job=olist_full_refresh,
    cron_schedule="0 2 * * *",      # 02:00 daily
    execution_timezone="Asia/Singapore",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=[bronze_raw_commerce, dbt_models],
    jobs=[olist_full_refresh, stg_only, gold_mart_only],
    schedules=[olist_nightly],
    resources={"dbt": dbt_resource},
)
```

### 4.2 Remove the baked-in env from the Dockerfile (G1, G2)

Edit `Dockerfile`: **delete** the `COPY .env.prod /app/.env.prod` line. The image carries no env
and no keyfile. At runtime, `run-dagster.sh` supplies `.env.prod` (`--env-file`) and mounts `.env.key`.

> `config.py` calls `load_dotenv(.env.prod)` only *if the file exists*, and `load_dotenv` does
> **not** override real environment variables — so values injected via `docker --env-file` take
> effect cleanly whether or not the file is baked in.

No `dagster.yaml` is required: `dagster dev` uses SQLite under `DAGSTER_HOME` by default, and we
make that path persistent via a Docker volume (§6.3).

---

## 5. Phase 1 — Build & push the image

> The **Dockerfile stays in the repo** (it's the build recipe). `gcloud builds submit` reads it
> and produces an **image** in Artifact Registry. The VM later pulls that image — it never sees
> the Dockerfile.

```bash
IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/olist-elt:latest

# 1) Artifact Registry repo (one-time)
gcloud artifacts repositories create $REPO \
  --repository-format=docker --location=$REGION \
  --description="Olist ELT images"

# 2) Build from REPO ROOT (the trailing "." = build context; must include
#    p3_dbt_project, p1_el, datasets/). Use --config (not --tag): the Dockerfile is in a
#    subfolder, so cloudbuild.yaml passes it with -f.
cd "$REPO_ROOT"
#    Option A: Cloud Build (no local Docker needed)
gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" .

#    Option B: local docker — must target amd64 for the x86 VM (Apple-silicon Macs build arm64):
# docker buildx build --platform linux/amd64 \
#   -f p6_orchestration/olist_orchestration/Dockerfile -t $IMAGE . --push
```

> Build context = repo root. `.dockerignore` already trims `my-work`, other `p*` folders,
> `.git`, venvs, secrets, `.env*`, etc. `datasets/` is intentionally **included** for the manual
> bronze load. The Dockerfile path is set in `cloudbuild.yaml`.

---

## 6. Phase 2 — Provision the VM and run Dagster

### 6.1 Create the VM with the SA attached

```bash
MACHINE_TYPE=e2-medium           # 2 vCPU / 4 GB — comfortable for dagster dev + dbt + runs
gcloud compute instances create olist-dagster \
  --zone=$ZONE \
  --machine-type=$MACHINE_TYPE \
  --image-family=cos-stable --image-project=cos-cloud \
  --service-account=$SA_EMAIL \
  --scopes=cloud-platform \
  --boot-disk-size=30GB \
  --tags=dagster-ui
```

> Container-Optimized OS (COS) ships Docker. The attached SA + `cloud-platform` scope let the VM
> pull the image from Artifact Registry. BigQuery auth comes from the mounted keyfile, not the VM SA.
>
> **Sizing:** `e2-medium` (4 GB) gives ample headroom — BigQuery does the heavy compute, and the
> VM only runs the Python glue (`dagster dev`'s 3 processes + a run worker + dbt). To trim cost
> later you can resize down to `e2-small` (2 GB); if you ever see an OOM-kill (container exit code
> 137), resize back up. Data persists on the boot disk + `dagster_home` volume across a resize:
> ```bash
> gcloud compute instances stop  olist-dagster --zone=$ZONE
> gcloud compute instances set-machine-type olist-dagster --zone=$ZONE --machine-type=e2-medium
> gcloud compute instances start olist-dagster --zone=$ZONE
> ```

### 6.2 Prepare the two prod config files (locally, to copy to the VM)

Both live at the **repo root**, next to `run-dagster.sh`, and are **git-ignored**.

**`.env.prod`** — non-sensitive config. Note `GOOGLE_APPLICATION_CREDENTIALS` points at the
in-container mount path (`/secrets/sa.json`), **not** a local path:

```dotenv
GCP_PROJECT=sctp-team2-project2-elt
BQ_LOCATION=US
BQ_BRONZE_DATASET=olist_bronze
BQ_STAGE_DATASET=olist_stage
BQ_GOLD_DATASET=olist_gold_mart
DBT_TARGET=prod
MELTANO_ENVIRONMENT=prod
OLIST_DATA_DIR=./datasets
BRONZE_LOAD_METHOD=manual
OLIST_ENV=prod
GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json
```

**`.env.key`** — the SA JSON keyfile itself (option b). Just copy your existing keyfile:

```bash
cd "$REPO_ROOT"
cp secrets/sctp-team2-project2-elt-1853e88c8665.json .env.key
```

> Both match the existing `**/.env.*` `.gitignore` rule, so neither is ever committed.

### 6.3 run-dagster.sh (repo root — already in the repo)

COS ships `docker` but **not** the `docker compose` plugin, so we launch the single container
with plain `docker` via the committed `run-dagster.sh`. It runs one `dagster dev` process
(webserver + daemon, like local `make dev`), SQLite on a persistent named volume, `.env.prod` as
env, `.env.key` mounted to `/secrets/sa.json`. The script also redeploys (pull latest + recreate).

> `dagster dev` prints a "not for production" notice — acceptable at this scale; the §14 upgrade
> path covers when to graduate to the split topology.

### 6.4 Bring it up

```bash
# Copy the launch script + both config files to the VM (from the repo root where they live)
cd "$REPO_ROOT"
gcloud compute scp run-dagster.sh .env.prod .env.key \
  olist-dagster:~ --zone=$ZONE

# SSH in and launch
gcloud compute ssh olist-dagster --zone=$ZONE
# --- on the VM ---
chmod 600 .env.key                       # lock down the keyfile
docker-credential-gcr configure-docker --registries=us-central1-docker.pkg.dev
# COS mounts /home noexec → invoke via `bash`, not ./
bash run-dagster.sh
docker ps
```

The bundled daemon starts the `olist_nightly` schedule automatically (we set
`default_status=RUNNING`).

---

## 7. Phase 3 — Secure & access the UI (no public exposure)

Port `:3000` is bound to localhost on the VM. Pick one access method:

**Quickest (SSH tunnel — recommended for a small team):**
```bash
gcloud compute ssh olist-dagster --zone=$ZONE -- -N -L 3000:localhost:3000
# then open http://localhost:3000 in your browser
```
Each teammate runs this with their own Google login; IAM (`roles/compute.osLogin` /
`iap.tunnelResourceAccessor`) controls who can tunnel — effectively free SSO.

**Or (IAP TCP forwarding, no SSH key juggling):**
```bash
gcloud compute start-iap-tunnel olist-dagster 3000 \
  --local-host-port=localhost:3000 --zone=$ZONE
```
Grant each teammate `roles/iap.tunnelResourceAccessor`.

> Do **not** add a `0.0.0.0` firewall rule for 3000. If you ever need a real hostname,
> front it with an HTTPS Load Balancer + IAP (OAuth login) instead.

---

## 8. Phase 4 — Reporting surfaces

### 8.1 Dagster UI (engineers / orchestration)
Already live from Phase 2–3: trigger `olist_full_refresh` / `stg_only` / `gold_mart_only`,
re-materialize individual assets, watch the nightly schedule, inspect logs and asset lineage.

### 8.2 BigQuery direct access (analysts / BI)
Grant teammates read on the gold layer (and stage if they want it):
```bash
for u in alice@gmail.com bob@gmail.com; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="user:$u" --role="roles/bigquery.jobUser"
done
# dataset-scoped viewer on gold_mart (tighter than project-wide):
bq show --format=prettyjson $PROJECT:olist_gold_mart > /tmp/gm.json
# edit access[] to add "READER" for each user, then:
bq update --source /tmp/gm.json $PROJECT:olist_gold_mart
```

### 8.3 Looker Studio dashboards (business users)
1. [lookerstudio.google.com](https://lookerstudio.google.com) → Create → Data source → **BigQuery**.
2. Project `sctp-team2-project2-elt` → dataset `olist_gold_mart` → tables `fact_orders`,
   `dim_customers`, `dim_sellers`, `dim_products`, `dim_reviews`.
3. Model the star: blend `fact_orders` to the dims on their keys (or build a Looker Studio
   "blend"). Suggested first dashboards: revenue by month/category, delivery-time distribution,
   review-score vs. delivery, top sellers/regions.
4. Share the report with the team (Looker Studio sharing); viewers need BQ read (8.2) **or**
   set the data source to "Owner's credentials" so viewers don't each need BQ access.

### 8.4 dbt docs site (data model reference)
Generate and host static docs:
```bash
make dbt-build ENV=prod          # ensures manifest is current
cd p3_dbt_project/brazil_ecommerce
dbt docs generate --profiles-dir . --target prod
# Host the static site cheaply on GCS:
gsutil mb -l $REGION gs://olist-dbt-docs
gsutil -m rsync -r target gs://olist-dbt-docs       # index.html, manifest, catalog
# (optional) serve behind the same IAP, or keep it bucket-private + share via signed URLs
```
> Easiest automation later: add a Dagster asset/op that runs `dbt docs generate` + `gsutil rsync`
> at the end of `olist_full_refresh` so docs refresh nightly.

---

## 9. Phase 5 — CI/CD (optional but recommended)

GitHub Actions on push to `main` → build image → push to Artifact Registry → restart the VM
container. The config files (`.env.prod`, `.env.key`) already live on the VM, so deploy is just
a pull + recreate. Sketch (`.github/workflows/deploy.yml`):

```yaml
on:
  push: { branches: [main], paths: ['p1_el/**','p3_dbt_project/**','p6_orchestration/**','datasets/**','Dockerfile'] }
  workflow_dispatch: {}
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions: { contents: read, id-token: write }   # Workload Identity Federation, no keyfile in GitHub
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with: { workload_identity_provider: ${{ secrets.WIF_PROVIDER }}, service_account: ${{ secrets.DEPLOY_SA }} }
      - run: gcloud builds submit --tag $IMAGE .
      - run: |   # recreate on the VM (config files already present there)
          gcloud compute ssh olist-dagster --zone=$ZONE --tunnel-through-iap --command \
            "bash run-dagster.sh"
```

Notes:
- **No git-ignored file dependency** (the old `COPY .env.prod` is gone), so the build is clean on a fresh checkout.
- **No keyfile in GitHub** — uses **Workload Identity Federation** to authenticate the Action.
- A **config change** is made directly on the VM (edit `~/.env.prod`, then `bash run-dagster.sh`) —
  no image rebuild needed.

---

## 10. Operations runbook

| Task | Command |
|---|---|
| Deploy new code | rebuild image (Phase 1) → on VM `bash run-dagster.sh` (pulls latest + recreates) |
| Change prod config | edit `~/.env.prod` on the VM → `bash run-dagster.sh` |
| Rotate the keyfile | replace `~/.env.key` on the VM (`chmod 600`) → `bash run-dagster.sh` |
| Tail logs | `docker logs -f olist-dagster` on the VM |
| Trigger a refresh now | Dagster UI → `olist_full_refresh` → Materialize all; or `docker exec olist-dagster dagster job execute -j olist_full_refresh -m olist_orchestration.definitions` |
| Run only a layer | UI jobs `stg_only` / `gold_mart_only` |
| dbt tests failing? | `olist_*_dbt_test__audit` tables in BQ hold failed rows (`store_failures: true`) |
| Restart | `docker restart olist-dagster` |
| VM recreate | re-run Phase 2 (the `dagster_home` volume persists run history unless the disk is deleted) |

---

## 11. Cost estimate (rough, monthly)

| Item | Est. |
|---|---|
| `e2-medium` VM (always-on, us-central1) | ~$24–28 |
| 30 GB boot disk | ~$1–2 |
| BigQuery storage (Olist ~ <1 GB) | < $0.10 |
| BigQuery query (nightly full refresh, small data) | a few cents |
| Artifact Registry storage | < $1 |
| Looker Studio / dbt-docs on GCS | ~free / pennies |
| **Total** | **~$27–31/mo** (resize to `e2-small` for ~$18 if you want to trim) |

Stop the VM (`gcloud compute instances stop olist-dagster`) when the course is idle to pause
VM billing.

---

## 12. Security checklist

- [ ] `.env.key` (SA keyfile) and `.env.prod` stay git-ignored (already match `**/.env.*`).
- [ ] `.env.key` is `chmod 600` on the VM; never baked into the image, never committed.
- [ ] Keyfile is mounted read-only (`:ro`) at `/secrets/sa.json`.
- [ ] Dagster `:3000` bound to `127.0.0.1`; access via SSH tunnel / IAP only.
- [ ] SA scoped to BigQuery + Artifact Registry read only (tighten BQ to per-dataset later).
- [ ] CI uses Workload Identity Federation, not a downloaded key.
- [ ] Looker Studio shared via "owner's credentials" or explicit BQ grants — not "anyone with link" on raw data.
- [ ] Consider key rotation at the end of the course (delete the SA key).

---

## 13. Validation checklist (done = deployed)

- [ ] Image builds from repo root and pushes to Artifact Registry.
- [ ] `bash run-dagster.sh` brings up the `olist-dagster` container; `docker ps` shows it `running`.
- [ ] Dagster UI reachable via tunnel; **no** `_dev` datasets shown (env = prod).
- [ ] Run history survives a `docker restart olist-dagster` (persistent `dagster_home` volume).
- [ ] Manual `olist_full_refresh` succeeds → `olist_bronze`, `olist_stage`, `olist_gold_mart`
      populated in BigQuery (`US`).
- [ ] Bronze verification (CSV-vs-BQ row counts in the asset logs) all ✅.
- [ ] `olist_nightly` schedule shows RUNNING in the UI.
- [ ] Looker Studio dashboard renders from `gold_mart`.
- [ ] Teammates can query `gold_mart` and/or open the dashboard.
- [ ] dbt docs site reachable.

---

## 14. Open items / future hardening

1. **Graduate to the split topology** (separate `dagster-webserver` + `dagster-daemon` + **Postgres**)
   if you hit SQLite locking or want concurrent runs. Adds a `dagster.yaml` (Postgres storage) and a
   Postgres password.
2. **Migrate to GKE / Dagster+** if the team outgrows a single VM (isolation, autoscaling).
3. **Drop the keyfile for ADC** — attaching the SA to the VM already gives ADC; removing
   `GOOGLE_APPLICATION_CREDENTIALS` from `.env.prod` would let BigQuery use the VM SA directly and
   eliminate the one secret. (Kept the keyfile for now to mirror the local setup.)
4. **GCS + Meltano bronze** if data stops being static (decouple data from image).
5. **Per-dataset IAM** instead of project-wide `dataEditor`.
6. **dbt docs auto-publish** as a final asset in `olist_full_refresh`.
7. **Alerting** — Dagster run-failure sensor → email/Slack; or Cloud Monitoring on the VM.
8. **HTTPS LB + IAP** with a real hostname if SSH tunnels become a friction point.
```
