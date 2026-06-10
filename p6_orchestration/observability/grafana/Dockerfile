FROM grafana/grafana:11.1.0

USER root

# Bake the BigQuery datasource plugin so cold starts don't fetch it at runtime.
RUN grafana cli plugins install grafana-bigquery-datasource

# Provisioned datasources + dashboards (config as code; survives the stateless
# Cloud Run filesystem because it's loaded from the image on every start).
COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/   /var/lib/grafana/dashboards/

ENV GF_SERVER_HTTP_PORT=8080
EXPOSE 8080

USER grafana
