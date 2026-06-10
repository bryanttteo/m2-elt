# Olist Ops Portal — local run, container build & Cloud Run deploy.
# Override on the CLI, e.g. `make deploy PROJECT=... REGION=...`.
PROJECT    ?= sctp-team2-project2-elt
REGION     ?= us-central1
ZONE       ?= us-central1-a
REPO       ?= olist-elt
SERVICE    ?= olist-ops-portal
IMAGE      ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE):latest
PORT       ?= 8080
PY         ?= .venv/bin/python

# Runtime identity. Cloud Run runs AS this service account (no key baked in).
# For local runs, the matching key file in ./secrets/ is used via ADC.
RUN_SA     ?= sctp-team2-project2-elt@$(PROJECT).iam.gserviceaccount.com
KEY_FILE   ?= secrets/sctp-team2-project2-elt-ROTATED-dbcb3cd092f4.json

# App URLs the portal links to AND health-checks. Fill these in (or pass on the CLI).
DASH_URL       ?=
STREAMLIT_URL  ?=
WORDCLOUD_URL  ?=
SUPERSET_URL   ?=
DAGSTER_URL    ?=

.PHONY: help venv run docker-build docker-run deploy clean

help:
	@echo "make venv          - create .venv and install requirements"
	@echo "make run           - run locally on :$(PORT)"
	@echo "make docker-build  - build the container image"
	@echo "make docker-run    - run the image locally"
	@echo "make deploy        - build via Cloud Build + deploy to Cloud Run"

venv:
	python3.11 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

run:
	GOOGLE_APPLICATION_CREDENTIALS=$(KEY_FILE) \
	  DASH_URL=$(DASH_URL) STREAMLIT_URL=$(STREAMLIT_URL) WORDCLOUD_URL=$(WORDCLOUD_URL) \
	  SUPERSET_URL=$(SUPERSET_URL) DAGSTER_URL=$(DAGSTER_URL) PORT=$(PORT) $(PY) app.py

docker-build:
	docker build -t $(SERVICE):local .

docker-run:
	docker run --rm -p $(PORT):8080 -e PORT=8080 \
	  -v $(PWD)/$(KEY_FILE):/secrets/sa.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json \
	  -e DASH_URL=$(DASH_URL) -e STREAMLIT_URL=$(STREAMLIT_URL) -e WORDCLOUD_URL=$(WORDCLOUD_URL) \
	  -e SUPERSET_URL=$(SUPERSET_URL) -e DAGSTER_URL=$(DAGSTER_URL) $(SERVICE):local

# Cloud Run deploy. The runtime SA needs read-only Cloud Run + Compute access for
# deploy/VM detection: roles/run.viewer + roles/compute.viewer (see README).
deploy:
	gcloud builds submit --tag $(IMAGE) --project $(PROJECT) .
	gcloud run deploy $(SERVICE) --image $(IMAGE) --project $(PROJECT) --region $(REGION) \
	  --platform managed --allow-unauthenticated --memory 512Mi --cpu 1 \
	  --service-account $(RUN_SA) \
	  --set-env-vars GCP_PROJECT=$(PROJECT),GCP_REGION=$(REGION),GCP_ZONE=$(ZONE),DASH_URL=$(DASH_URL),STREAMLIT_URL=$(STREAMLIT_URL),WORDCLOUD_URL=$(WORDCLOUD_URL),SUPERSET_URL=$(SUPERSET_URL),DAGSTER_URL=$(DAGSTER_URL)

clean:
	rm -rf __pycache__ */__pycache__
