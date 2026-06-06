.PHONY: setup pull run pipeline clean

# Canonical naming comes from .env (GCP_PROJECT / BQ_BRONZE_DATASET / BQ_LOCATION /
# OLIST_GCS_BUCKET). Fall back to dev defaults if a var is unset.
include .env
export
GCP_PROJECT       ?= sctp-team2-project2-elt
BQ_BRONZE_DATASET ?= olist_bronze_dev
BQ_LOCATION       ?= US
OLIST_GCS_BUCKET  ?= m2_olin_raw

setup:
	mkdir -p data/raw
	bq mk -d --location=$(BQ_LOCATION) $(GCP_PROJECT):$(BQ_BRONZE_DATASET) || true
	meltano install

# Optional load path: pull CSVs from GCS instead of using the local datasets/ copy.
pull:
	mkdir -p data/raw
	gsutil -m cp gs://$(OLIST_GCS_BUCKET)/*.csv data/raw/

run:
	meltano run olin-pipeline

pipeline: pull run

clean:
	rm -rf data/raw .meltano output
