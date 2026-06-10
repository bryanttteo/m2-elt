# Olist Grafana — self-hosted on Cloud Run, provisioned datasources + dashboards.
PROJECT     ?= sctp-team2-project2-elt
REGION      ?= us-central1
REPO        ?= olist-elt
SERVICE     ?= olist-grafana
IMAGE       ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE):latest
RUN_SA      ?= sctp-team2-project2-elt@$(PROJECT).iam.gserviceaccount.com
ADMIN_PASS  ?= changeme-$(PROJECT)

.PHONY: help docker-build docker-run deploy

help:
	@echo "make docker-build  - build the Grafana image (bakes plugin + provisioning)"
	@echo "make docker-run    - run locally on :3000 (admin / \$$ADMIN_PASS)"
	@echo "make deploy        - build via Cloud Build + deploy to Cloud Run"

docker-build:
	docker build -t $(SERVICE):local .

docker-run:
	docker run --rm -p 3000:8080 -e GF_SECURITY_ADMIN_PASSWORD=$(ADMIN_PASS) $(SERVICE):local

# Anonymous Viewer is enabled so the manager just opens the URL; editing needs
# the admin login. Runs AS the pipeline SA (gce auth for both datasources).
deploy:
	gcloud builds submit --tag $(IMAGE) --project $(PROJECT) .
	gcloud run deploy $(SERVICE) --image $(IMAGE) --project $(PROJECT) --region $(REGION) \
	  --platform managed --allow-unauthenticated --memory 1Gi --cpu 1 \
	  --service-account $(RUN_SA) \
	  --set-env-vars GF_SECURITY_ADMIN_PASSWORD=$(ADMIN_PASS),GF_AUTH_ANONYMOUS_ENABLED=true,GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer,GF_USERS_DEFAULT_THEME=dark,GF_USERS_VIEWERS_CAN_EDIT=false
