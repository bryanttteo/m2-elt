# Olist review text-analysis app (Streamlit) — local run, container & Cloud Run deploy.
# Always queries BigQuery live (results cached in-session). Config (override on the CLI):
ENV        ?= prod
PROJECT    ?= sctp-team2-project2-elt
REGION     ?= us-central1
REPO       ?= olist-elt
SERVICE    ?= olist-wordcloud
IMAGE      ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE):latest
PORT       ?= 8502
PY         ?= .venv/bin/python

# Runtime identity. Cloud Run runs AS this service account (no key baked in); it holds
# BigQuery access so the live dim_reviews queries work. Matches the pipeline SA used by
# the other prod services. Locally, use the matching key in ../../secrets/ for ADC.
RUN_SA     ?= sctp-team2-project2-elt@$(PROJECT).iam.gserviceaccount.com

.PHONY: help venv run docker-build docker-run deploy clean

help:
	@echo "make venv          - create .venv (Python 3.11) and install requirements"
	@echo "make run           - run the app locally (ENV=$(ENV)) on :$(PORT)"
	@echo "make docker-build  - build the container image"
	@echo "make docker-run    - run the image locally"
	@echo "make deploy        - build via Cloud Build + deploy to Cloud Run"

venv:
	python3.11 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

run:
	ENV=$(ENV) .venv/bin/streamlit run app.py --server.port=$(PORT)

docker-build:
	docker build -t $(SERVICE):local .

docker-run:
	docker run --rm -p $(PORT):8080 -e PORT=8080 $(SERVICE):local

deploy:
	gcloud builds submit --tag $(IMAGE) --project $(PROJECT) .
	gcloud run deploy $(SERVICE) --image $(IMAGE) --project $(PROJECT) --region $(REGION) \
	  --platform managed --allow-unauthenticated --memory 1Gi --cpu 1 --port 8080 \
	  --service-account $(RUN_SA)

clean:
	rm -rf __pycache__ */__pycache__
