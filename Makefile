# ─────────────────────────────────────────────────────────────────────────────
# Olist ELT — developer entrypoints.
# Naming/config comes from .env.<ENV> at repo root (see .env.example).
# Usage:  make dev | make prod | make jun | make dbt-build ENV=jun | make meltano-run
#
# NOTE: recipes are written as single shell invocations (`; \` continuations)
# because macOS ships GNU make 3.81, which ignores `.ONESHELL:` — otherwise each
# line runs in its own shell and the sourced .env vars are lost before dbt runs.
# ─────────────────────────────────────────────────────────────────────────────
SHELL := /bin/bash

ENV     ?= dev
P6      := p6_orchestration/olist_orchestration
DBT     := p3_dbt_project/brazil_ecommerce
MELTANO := p1_el/meltano-raw-csv

# One target per personal env file (.env.<name>), so `make jun` == `make dev ENV=jun`.
# Reserved target names are excluded so a stray .env.dev/.env.example can't shadow them.
RESERVED   := help install dev prod dbt-deps dbt-build dbt-test meltano-run example
NAMED_ENVS := $(filter-out $(RESERVED),$(patsubst .env.%,%,$(wildcard .env.*)))

.PHONY: help install dev prod dbt-deps dbt-build dbt-test meltano-run $(NAMED_ENVS)

help:
	@echo "Targets (all honour ENV=<name> -> loads .env.<name>, default dev):"
	@echo "  install      pip install the Dagster project (editable, with dev extras)"
	@echo "  dev          run 'dagster dev' with .env.\$$(ENV)   (web UI on :3000)"
	@echo "  prod         shortcut for 'make dev ENV=prod'"
	@echo "  <name>       shortcut for 'make dev ENV=<name>' for each .env.<name> file"
	@echo "  dbt-build    dbt deps + dbt build against .env.\$$(ENV)"
	@echo "  dbt-test     dbt test against .env.\$$(ENV)"
	@echo "  meltano-run  run the Meltano tap-csv -> target-bigquery pipeline"
	@echo ""
	@echo "  Examples:  make dev      make jun      make dbt-build ENV=jun"
	@echo "             Personal sandboxes use the .env.<name> convention (git-ignored)."
	@echo "  Detected personal envs: $(NAMED_ENVS)"

install:
	cd $(P6) && pip install -e '.[dev]'

# Dagster reads .env.<ENV> itself via olist_orchestration.config (OLIST_ENV).
dev:
	cd $(P6) && OLIST_ENV=$(ENV) dagster dev

prod:
	$(MAKE) dev ENV=prod

# `make jun`, `make <teammate>`, ... -> dagster dev on that env's datasets.
$(NAMED_ENVS):
	cd $(P6) && OLIST_ENV=$@ dagster dev

dbt-deps:
	cd $(DBT) && dbt deps

# Single shell: source .env.<ENV>, resolve the (repo-root-relative) keyfile to an
# absolute path, then run dbt with env-var-driven project/dataset/location.
dbt-build: dbt-deps
	set -a; source .env.$(ENV); set +a; \
	export GOOGLE_APPLICATION_CREDENTIALS=$$(python3 -c "import os;print(os.path.abspath(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))"); \
	cd $(DBT) && dbt build --profiles-dir .

dbt-test:
	set -a; source .env.$(ENV); set +a; \
	export GOOGLE_APPLICATION_CREDENTIALS=$$(python3 -c "import os;print(os.path.abspath(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))"); \
	cd $(DBT) && dbt test --profiles-dir .

meltano-run:
	cd $(MELTANO) && meltano run olin-pipeline
