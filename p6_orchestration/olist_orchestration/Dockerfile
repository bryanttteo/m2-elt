# Olist ELT orchestration image (Dagster + dbt-bigquery + Meltano).
#
# Build from the REPO ROOT (the build context must include p3_dbt_project,
# p1_el/olist-meltano-pg and datasets/):
#
#   docker build -f p6_orchestration/olist_orchestration/Dockerfile -t olist-elt:latest .
#
# PROD: this image runs on a Compute Engine VM (Container-Optimized OS), launched by
# run-dagster.sh with plain `docker run` (see notes/setup.prod.md). Config comes from
# two VM-only files: .env.prod (non-sensitive, passed via --env-file) and .env.key (the
# SA keyfile, mounted to /secrets/sa.json, referenced by GOOGLE_APPLICATION_CREDENTIALS
# in .env.prod). The default CMD below is a one-shot full refresh; run-dagster.sh overrides
# it with `dagster dev` to serve the always-on UI + daemon (schedules).
#
FROM python:3.11-slim

# Version stamp — passed by the build (git short SHA, see cloudbuild.yaml). Surfaced as
# the APP_VERSION env var (visible in the Dagster process / `docker exec ... env`) and an
# OCI revision label (`docker inspect`), so a running container traces to an exact commit.
ARG APP_VERSION=dev
LABEL org.opencontainers.image.revision=$APP_VERSION

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DAGSTER_HOME=/opt/dagster/home \
    OLIST_ENV=prod \
    APP_VERSION=$APP_VERSION

# git is needed: Meltano installs tap-csv / target-bigquery from git pip_urls.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p $DAGSTER_HOME

WORKDIR /app

# Copy the pieces the pipeline touches (paths relative to the repo-root context).
COPY p6_orchestration/olist_orchestration/ /app/p6_orchestration/olist_orchestration/
COPY p3_dbt_project/                        /app/p3_dbt_project/
COPY p1_el/olist-meltano-pg/                 /app/p1_el/olist-meltano-pg/
COPY datasets/                               /app/datasets/
# NOTE: .env.prod is intentionally NOT baked in (it is git-ignored, which would break
# clean CI builds). Prod config is injected at runtime by run-dagster.sh via
# `docker --env-file .env.prod`; the SA keyfile is mounted from .env.key. See notes/setup.prod.md.

# Install the orchestration package + its deps, plus the runtime tools.
RUN pip install -e /app/p6_orchestration/olist_orchestration \
    && pip install dagster-webserver meltano

# Pre-fetch dbt packages so the image is self-contained.
RUN cd /app/p3_dbt_project/brazil_ecommerce && dbt deps || true

# Pre-install Meltano plugins for the postgres bronze load path so `meltano run` works
# at runtime without a network install step (tap-postgres, target-bigquery).
RUN cd /app/p1_el/olist-meltano-pg && meltano install || true

WORKDIR /app/p6_orchestration/olist_orchestration

# One-shot execution for Cloud Run jobs. For a long-running UI (Cloud Run service)
# override with:  dagster dev -h 0.0.0.0 -p 3000
CMD ["dagster", "job", "execute", "-m", "olist_orchestration.definitions", "-j", "olist_full_refresh"]
