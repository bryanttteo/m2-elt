# Olist executive dashboard — local run, snapshot, container build & Cloud Run deploy.
# Config (override on the CLI, e.g. `make run ENV=dev`):
ENV        ?= prod
PROJECT    ?= sctp-team2-project2-elt
REGION     ?= us-central1
REPO       ?= olist-elt
SERVICE    ?= olist-dash
IMAGE      ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE):latest
PORT       ?= 8050
PY         ?= .venv/bin/python

.PHONY: help venv run snapshot docker-build docker-run deploy clean

help:
	@echo "make venv          - create .venv (Python 3.11) and install requirements"
	@echo "make run           - run the app locally (ENV=$(ENV)) on :$(PORT)"
	@echo "make snapshot      - rebuild the parquet cache in data/ from BigQuery"
	@echo "make docker-build  - build the container image (bakes data/ if present)"
	@echo "make docker-run    - run the image locally in offline (snapshot) mode"
	@echo "make deploy        - build via Cloud Build + deploy to Cloud Run"

venv:
	python3.11 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

run:
	ENV=$(ENV) PORT=$(PORT) $(PY) app.py

snapshot:
	ENV=$(ENV) $(PY) app.py --snapshot

docker-build:
	docker build -t $(SERVICE):local .

docker-run:
	docker run --rm -p $(PORT):8080 -e DASH_OFFLINE=1 -e PORT=8080 $(SERVICE):local

# Cloud Run deploy. Live-BQ mode (default): the runtime SA needs BigQuery access (see
# notes/setup.prod.md). For a fully offline image, run `make snapshot` first and add
# `--set-env-vars DASH_OFFLINE=1`.
deploy:
	gcloud builds submit --tag $(IMAGE) --project $(PROJECT) .
	gcloud run deploy $(SERVICE) --image $(IMAGE) --project $(PROJECT) --region $(REGION) \
	  --platform managed --allow-unauthenticated --memory 1Gi --cpu 1 \
	  --set-env-vars ENV=prod,GCP_PROJECT=$(PROJECT),BQ_LOCATION=US,BQ_GOLD_DATASET=olist_gold_mart_prod

clean:
	rm -rf data/*.parquet __pycache__ */__pycache__
