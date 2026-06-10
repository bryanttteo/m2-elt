# Olist executive dashboard (Streamlit) — local run, snapshot, container & Cloud Run deploy.
# Config (override on the CLI, e.g. `make run ENV=dev`):
ENV        ?= prod
PROJECT    ?= sctp-team2-project2-elt
REGION     ?= us-central1
REPO       ?= olist-elt
SERVICE    ?= olist-streamlit
IMAGE      ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE):latest
PORT       ?= 8501
PY         ?= .venv/bin/python

.PHONY: help venv run snapshot docker-build docker-run deploy clean

help:
	@echo "make venv          - create .venv (Python 3.11) and install requirements"
	@echo "make run           - run the app locally (ENV=$(ENV)) on :$(PORT)"
	@echo "make snapshot      - rebuild the parquet cache in data/ from BigQuery"
	@echo "make docker-build  - build the container image (bakes data/)"
	@echo "make docker-run    - run the image locally in offline (snapshot) mode"
	@echo "make deploy        - build via Cloud Build + deploy to Cloud Run"

venv:
	python3.11 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

run:
	ENV=$(ENV) .venv/bin/streamlit run app.py --server.port=$(PORT)

snapshot:
	ENV=$(ENV) DASH_OFFLINE=0 $(PY) app.py --snapshot

docker-build:
	docker build -t $(SERVICE):local .

docker-run:
	docker run --rm -p $(PORT):8080 -e PORT=8080 $(SERVICE):local

deploy:
	gcloud builds submit --tag $(IMAGE) --project $(PROJECT) .
	gcloud run deploy $(SERVICE) --image $(IMAGE) --project $(PROJECT) --region $(REGION) \
	  --platform managed --allow-unauthenticated --memory 1Gi --cpu 1 --port 8080 \
	  --set-env-vars DASH_OFFLINE=1

clean:
	rm -rf __pycache__ */__pycache__
