# Prod setup — Olist ELT on Google Cloud

Hands-on runbook for deploying Meltano + dbt + Dagster to prod. For the *why* behind each
choice, see [`plan/plan2-prod-deploy.md`](../plan/plan2-prod-deploy.md).

## TL;DR

- **One `e2-medium` VM** (2 vCPU / 4 GB) runs **one `dagster dev` container**
  (webserver + daemon, just like local `make dev`).
- The team opens the **Dagster UI** through an SSH tunnel and materializes assets; a **nightly
  schedule** (02:00 SGT) runs `olist_full_refresh` automatically.
- Prod config = two **VM-only, git-ignored** files at the repo root:
  - `.env.prod` — non-sensitive config (project / datasets / targets).
  - `.env.key` — the **service-account JSON keyfile**, mounted to `/secrets/sa.json`.
- Results land in BigQuery (`olist_bronze → olist_stage → olist_gold_mart`, US) and are consumed
  via **Looker Studio**, **direct BigQuery access**, the **Dagster UI**, and a **dbt docs site**.

```
e2-medium VM ─▶ dagster dev (UI :3000 + daemon) ──▶ Meltano/load + dbt ──▶ BigQuery (US)
                                                                              │
                                              Looker Studio · BigQuery · dbt docs · Dagster UI
```

---

## 0. What's already done in the repo (Phase 0)

These are committed — you don't need to redo them:

- `definitions.py` — `olist_nightly` schedule (fires 02:00 **Singapore _time_** — a clock setting
  for when the run triggers, **not** a GCP region; all infra is US). `default_status=RUNNING`.
- `Dockerfile` — no longer bakes `.env.prod`; documents the keyfile-mount approach.
- `run-dagster.sh` (repo root) — launches/redeploys the single `dagster dev` container on the
  VM: persistent `dagster_home` volume, `.env.prod` as env, `.env.key` mounted to `/secrets/sa.json`.
- `cloudbuild.yaml` (repo root) — builds the image (Dockerfile lives in a subfolder).

---

## Where to run each step

Unless a step says **🖥️ on the VM**, run it on your **local machine** (your Mac terminal, from
`$REPO_ROOT`). Local steps just need `gcloud` installed + `gcloud auth login` done.

| Step | Runs on |
|---|---|
| §1 set vars · §2 GCP setup · §3 build image · §4 config files · §5 create VM | 🧑‍💻 local Mac |
| §6 deploy — the `scp` is local; then you SSH in and the `run-dagster.sh` / `docker` commands are | 🖥️ on the VM |
| §7 open UI (`ssh -L` tunnel) · §8 reporting · §9 ops (mixed — marked inline) | 🧑‍💻 local unless noted |

> `gcloud builds submit`, `gcloud compute …`, `scp` all run **locally** and talk to GCP over the
> network. Only commands *after* you `gcloud compute ssh` into the VM run on the VM itself.

## 1. Set shell variables

```bash
# Repo root — where run-dagster.sh, cloudbuild.yaml, .env.*, Makefile, datasets/ live.
# (Adjust to wherever you cloned the repo.)
export REPO_ROOT=/Users/cheonghoongjun/Documents/dev/github-dev/sctp-dsai-forked/dsai-m2-elt/m2-elt
cd "$REPO_ROOT"

export PROJECT=sctp-team2-project2-elt
export REGION=us-central1
export ZONE=us-central1-a
export REPO=olist-elt
export IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/olist-elt:latest
export SA_EMAIL=sctp-team2-project2-elt@$PROJECT.iam.gserviceaccount.com
gcloud config set project $PROJECT
```

## 2. One-time GCP setup

```bash
# Enable APIs
gcloud services enable \
  compute.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com bigquery.googleapis.com iap.googleapis.com

# IAM on the existing project SA (whose keyfile you already use locally)
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA_EMAIL" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA_EMAIL" --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA_EMAIL" --role="roles/artifactregistry.reader"

# Artifact Registry repo (ALREADY_EXISTS error here is harmless — it just means it's made)
gcloud artifacts repositories create $REPO \
  --repository-format=docker --location=$REGION --description="Olist ELT images"

# Cloud Build runs as the DEFAULT COMPUTE service account — grant it the builder role,
# or `gcloud builds submit` fails with a storage.objects.get 403 on the source bucket.
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

## 3. Build & push the image

Run from the **repo root** (the build context needs `p3_dbt_project/`, `p1_el/`, `datasets/`):

```bash
cd "$REPO_ROOT"                  # the trailing "." below is this dir = the build context
# --config (not --tag): the Dockerfile is in a subfolder, so cloudbuild.yaml passes it via -f.
gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" .
# Local alternative (needs Docker + amd64 build for the x86 VM):
# docker buildx build --platform linux/amd64 \
#   -f p6_orchestration/olist_orchestration/Dockerfile -t $IMAGE . --push
```

> You should see it archive **hundreds** of files (the whole repo-root context). If it says
> "~40 files", you're in the wrong directory — `cd "$REPO_ROOT"` and retry.

## 4. Prepare the two prod config files (repo root, git-ignored)

### `.env.prod`

Check the team Google Drive first — a pre-filled `.env.prod` may already be there:
> **[Google Drive → SCTP Team2 → keys](https://drive.google.com/drive/u/1/folders/16cAsp_Pcq10lgHRpRnOQkW1scUHejuGe)**
>
> Download `.env.prod` from there and copy it to `$REPO_ROOT`.

If it's not in Drive, create it manually — note `GOOGLE_APPLICATION_CREDENTIALS` points at the *in-container* mount path:

```dotenv
GCP_PROJECT=sctp-team2-project2-elt
BQ_LOCATION=US
BQ_BRONZE_DATASET=olist_bronze_prod
BQ_STAGE_DATASET=olist_stage_prod
BQ_GOLD_DATASET=olist_gold_mart_prod
DBT_TARGET=prod
MELTANO_ENVIRONMENT=prod
OLIST_DATA_DIR=./datasets
BRONZE_LOAD_METHOD=meltano_postgres
OLIST_ENV=prod
GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json
# Cloud SQL PostgreSQL — direct connection to instance sctp-m2-olist (public IP, no proxy).
# Required by the tap-postgres → BigQuery bronze job (p1_el/olist-meltano-pg).
POSTGRES_HOST=34.121.52.84
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=SCTP-Team2-olist
POSTGRES_DB=olist
POSTGRES_SCHEMA=oltp
```

> The Postgres tap authenticates with username/password over the instance's **public IP**
> (`ssl: true`), **not** the Cloud SQL Auth Proxy or IAM auth — so the service account needs
> **no** `roles/cloudsql.*` binding. The only network requirement is that the VM's external IP
> is in the instance's **authorized networks** (the nightly-recreated VM gets a new IP each
> morning — see §11 — so confirm `0.0.0.0/0` is allowed or re-authorize daily).

#### Switching the bronze load method

`BRONZE_LOAD_METHOD` chooses how bronze is populated. Prod defaults to **`meltano_postgres`**
(the live Cloud SQL OLTP source). To switch, edit the value in `~/.env.prod` **on the VM** and
recreate the container — no image rebuild needed (it's runtime config):

| Value | Source | Meltano project |
|---|---|---|
| `meltano_postgres` *(default)* | Cloud SQL `oltp.*` | `p1_el/olist-meltano-pg` (tap-postgres) |
| `meltano_csv` (alias `meltano`) | baked-in `datasets/*.csv` | `p1_el/meltano-raw-csv` (tap-csv) |
| `manual` | baked-in `datasets/*.csv` | — (code path in `assets.py`) |

```bash
# 🖥️ on the VM
sed -i 's/^BRONZE_LOAD_METHOD=.*/BRONZE_LOAD_METHOD=manual/' ~/.env.prod   # e.g. fall back to CSV
bash run-dagster.sh                                                        # recreate with new env
```

> `meltano_postgres` requires the `POSTGRES_*` block above **and** the VM IP authorized on the
> Cloud SQL instance. If Postgres is unreachable, switch to `manual`/`meltano_csv` to load the
> CSVs bundled in the image. All three land in the same `olist_*_raw` bronze tables.
> The Meltano `prod` environment is declared in `p1_el/olist-meltano-pg/meltano.yml` (the
> orchestration runs `meltano --environment=prod run tap-postgres target-bigquery`).

### `.env.key` (service-account keyfile)

Check if the keyfile already exists locally:
```bash
ls "$REPO_ROOT/secrets/sctp-team2-project2-elt-ROTATED-dbcb3cd092f4.json"
```

If it's **missing**, download it from the team Google Drive:
> **[Google Drive → SCTP Team2 → keys](https://drive.google.com/drive/u/1/folders/16cAsp_Pcq10lgHRpRnOQkW1scUHejuGe)**
>
> Download `sctp-team2-project2-elt-ROTATED-dbcb3cd092f4.json` and place it in `secrets/`.

Then copy it to `.env.key` (the name the container expects):
```bash
cd "$REPO_ROOT"
cp secrets/sctp-team2-project2-elt-ROTATED-dbcb3cd092f4.json .env.key
```

> Both `.env.prod` and `.env.key` match `**/.env.*` in `.gitignore` — neither is committed. They live on the VM only.

## 5. Create the VM

```bash
export MACHINE_TYPE=e2-medium         # 2 vCPU / 4 GB — comfortable headroom
gcloud compute instances create olist-dagster \
  --zone=$ZONE --machine-type=$MACHINE_TYPE \
  --image-family=cos-stable --image-project=cos-cloud \
  --service-account=$SA_EMAIL --scopes=cloud-platform \
  --boot-disk-size=30GB --tags=dagster-ui
```

## 6. Deploy (copy files + start the container)

> COS ships `docker` but **not** the `docker compose` plugin, so we launch the single container
> directly via the committed **`run-dagster.sh`** (it also redeploys: pulls latest + recreates).

**6a. 🧑‍💻 Copy the script + both config files to the VM** (local, from repo root):
```bash
cd "$REPO_ROOT"
gcloud compute scp run-dagster.sh .env.prod .env.key olist-dagster:~ --zone=$ZONE
```

**6b. 🧑‍💻 SSH in** (local):
```bash
gcloud compute ssh olist-dagster --zone=$ZONE
```

**6c. 🖥️ On the VM** — the scp'd files are in your home dir; run from there:
```bash
chmod 600 .env.key
# Let Docker authenticate to Artifact Registry using the VM's attached service account:
docker-credential-gcr configure-docker --registries=us-central1-docker.pkg.dev
# Launch. COS mounts /home noexec, so invoke via `bash` (not ./). First boot runs `dbt deps`
# + parse, so give it a minute.
bash run-dagster.sh
docker ps
docker logs -f olist-dagster          # watch it come up; Ctrl-C stops tailing (container keeps running)
```

The bundled daemon arms the `olist_nightly` schedule automatically.

## 7. Open the Dagster UI (each teammate)

Port 3000 is bound to localhost on the VM — reach it over an SSH tunnel:

```bash
gcloud compute ssh olist-dagster --zone=$ZONE -- -N -L 3000:localhost:3000
# then open http://localhost:3000
```

In the UI: open **Jobs → `olist_full_refresh` → Materialize all** for the first run, or wait for
the nightly schedule. Narrower jobs: `stg_only`, `gold_mart_only`.

> Don't open port 3000 to the internet (the UI has no auth). To grant access without SSH keys,
> use IAP instead: grant `roles/iap.tunnelResourceAccessor`, then
> `gcloud compute start-iap-tunnel olist-dagster 3000 --local-host-port=localhost:3000 --zone=$ZONE`.

## 8. Reporting surfaces for the team

- **Dagster UI** — pipeline health, lineage, manual materializes (§7).
- **BigQuery direct access** — grant teammates read:
  ```bash
  gcloud projects add-iam-policy-binding $PROJECT --member="user:NAME@gmail.com" --role="roles/bigquery.jobUser"
  # + dataset READER on olist_gold_mart (bq update --source)
  ```
- **Looker Studio** — new BigQuery data source → `olist_gold_mart` → `fact_orders` + `dim_*`;
  build dashboards; share with "Owner's credentials" so viewers don't each need BQ access.
- **dbt docs** —
  ```bash
  cd "$REPO_ROOT"
  make dbt-build ENV=prod
  cd "$REPO_ROOT/p3_dbt_project/brazil_ecommerce" && dbt docs generate --profiles-dir . --target prod
  gsutil mb -l $REGION gs://olist-dbt-docs && gsutil -m rsync -r target gs://olist-dbt-docs
  ```

## 9. Day-2 operations

| Task | Command (on the VM unless noted) |
|---|---|
| Deploy new code | (local) rebuild image §3 → (VM) `bash run-dagster.sh` (pulls latest + recreates) |
| Change prod config | edit `~/.env.prod` → `bash run-dagster.sh` |
| Rotate keyfile | replace `~/.env.key` (`chmod 600`) → `bash run-dagster.sh` |
| Logs | `docker logs -f olist-dagster` |
| Run now (CLI) | `docker exec olist-dagster dagster job execute -j olist_full_refresh -m olist_orchestration.definitions` |
| Restart | `docker restart olist-dagster` |
| Resize VM (e.g. trim to `e2-small`, or up after an OOM exit 137) | (local) `gcloud compute instances stop olist-dagster --zone=$ZONE` → `... set-machine-type ... --machine-type=e2-medium` → `... start ...` |
| Pause billing when idle | (local) `gcloud compute instances stop olist-dagster --zone=$ZONE` |

## 10. Validation checklist

- [ ] `docker ps` shows `olist-dagster` running.
- [ ] UI reachable via tunnel; datasets show **no** `_dev` suffix (prod).
- [ ] `olist_full_refresh` succeeds → `olist_bronze` / `olist_stage` / `olist_gold_mart` populated in BigQuery (US).
- [ ] Bronze row-count verification in the asset logs all ✅.
- [ ] `olist_nightly` schedule shows **RUNNING**.
- [ ] Run history survives `docker restart olist-dagster` (persistent `dagster_home` volume).
- [ ] Looker Studio dashboard renders from `gold_mart`; teammates can query / view it.
- [ ] dbt docs site reachable.

---

## 11. Daily redeploy (delete VM each night, recreate each morning)

> Run all commands from your **local Mac** (`$REPO_ROOT`). Set vars first (§1).

### 11a. Morning — recreate VM and deploy

```bash
# 1. Set vars (copy-paste §1 block)
export REPO_ROOT=/Users/cheonghoongjun/Documents/dev/github-dev/sctp-dsai-forked/dsai-m2-elt/m2-elt
export PROJECT=sctp-team2-project2-elt
export REGION=us-central1
export ZONE=us-central1-a
export SA_EMAIL=sctp-team2-project2-elt@$PROJECT.iam.gserviceaccount.com
gcloud config set project $PROJECT

# 2. Create VM (same as §5)
gcloud compute instances create olist-dagster \
  --zone=$ZONE --machine-type=e2-medium \
  --image-family=cos-stable --image-project=cos-cloud \
  --service-account=$SA_EMAIL --scopes=cloud-platform \
  --boot-disk-size=30GB --tags=dagster-ui

# 3. Copy config files + scripts to VM (same as §6a)
cd "$REPO_ROOT"
gcloud compute scp run-dagster.sh .env.prod .env.key olist-dagster:~ --zone=$ZONE

# 4. SSH in and start the container
gcloud compute ssh olist-dagster --zone=$ZONE --command="
  chmod 600 .env.key
  docker-credential-gcr configure-docker --registries=us-central1-docker.pkg.dev
  bash run-dagster.sh
  docker ps
"

# 5. Add team2 to nginx basic auth (run each time — file lives on the VM)
gcloud compute ssh olist-dagster --zone=$ZONE --command="
  HASH=\$(openssl passwd -apr1 'password')
  echo \"team2:\$HASH\" >> ~/dagster.htpasswd
  docker exec dagster-proxy nginx -s reload
"
```

> UI is at `http://<VM-external-ip>:3000` — login: `team2` / `password`.  
> Get the new IP with: `gcloud compute instances describe olist-dagster --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`

### 11b. Evening — delete VM to stop billing

```bash
gcloud compute instances delete olist-dagster --zone=$ZONE --quiet
```

---

## Notes / gotchas

- **`dagster dev` prints a "not for production" warning** — expected and fine at this scale. It's
  what bundles the webserver + daemon into one process (same as local). See `plan2` §14 for when
  to graduate to the split webserver/daemon/Postgres topology.
- **Keyfile vs ADC** — we use a mounted keyfile (`.env.key`) to mirror local. Since the SA is also
  attached to the VM, you could drop `GOOGLE_APPLICATION_CREDENTIALS` from `.env.prod` and let
  BigQuery use the VM's ADC instead — removing the one secret. (`plan2` §14.3.)
- **Config files never enter the image or git** — they're `scp`'d to the VM and read at runtime.
- **BigQuery does the heavy compute** — dbt only issues SQL, so the VM mostly runs Python glue.
  `e2-medium` (4 GB) has ample headroom; you could trim to `e2-small` (2 GB) to save ~$13/mo if
  runs stay light.
