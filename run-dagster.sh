#!/usr/bin/env bash
# Launch / redeploy the Olist Dagster stack on the prod VM (Container-Optimized OS).
#
# Two containers on a private docker network (`dagnet`):
#   - olist-dagster : the Dagster app (webserver + daemon). Internal only — NOT published
#                     publicly (just 127.0.0.1:3001 on the VM for local checks).
#   - dagster-proxy : nginx with HTTP Basic Auth. The ONLY thing published to host :3000.
#
# So public :3000 always hits the password gate. Access is further limited by a firewall
# IP-allowlist (only your SG network). See notes/setup.prod.md.
#
# Requires in the current dir (your home dir on the VM): .env.prod, .env.key,
# nginx-dagster.conf, and dagster.htpasswd. Create the htpasswd once:
#   docker run --rm httpd:2.4-alpine htpasswd -nbB team 'YOUR_PASSWORD' > dagster.htpasswd
#
# Run with:  bash run-dagster.sh   (COS mounts /home noexec, so invoke via bash, not ./)
set -euo pipefail

IMAGE="${IMAGE:-us-central1-docker.pkg.dev/sctp-team2-project2-elt/olist-elt/olist-elt:latest}"

if [ ! -f "$PWD/dagster.htpasswd" ]; then
  echo "ERROR: dagster.htpasswd not found in $PWD. Create it first:"
  echo "  docker run --rm httpd:2.4-alpine htpasswd -nbB team 'YOUR_PASSWORD' > dagster.htpasswd"
  exit 1
fi

docker network create dagnet 2>/dev/null || true
docker pull "$IMAGE"

# Dagster app — internal only (reachable by the proxy via the docker network name).
docker rm -f olist-dagster 2>/dev/null || true
docker run -d --name olist-dagster --restart unless-stopped --network dagnet \
  -p 127.0.0.1:3001:3000 \
  --env-file "$PWD/.env.prod" \
  -e DAGSTER_HOME=/opt/dagster/home \
  -v dagster_home:/opt/dagster/home \
  -v dbt_docs:/opt/dbt-docs \
  -v "$PWD/.env.key:/secrets/sa.json:ro" \
  "$IMAGE" \
  dagster dev -h 0.0.0.0 -p 3000 -m olist_orchestration.definitions

# nginx Basic-Auth proxy — the only container published to public :3000.
# Also serves the static dbt docs site (shared dbt_docs volume) at /dbt-docs/.
docker rm -f dagster-proxy 2>/dev/null || true
docker run -d --name dagster-proxy --restart unless-stopped --network dagnet \
  -p 3000:3000 \
  -v "$PWD/nginx-dagster.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/dagster.htpasswd:/etc/nginx/.htpasswd:ro" \
  -v dbt_docs:/usr/share/nginx/dbt-docs:ro \
  nginx:stable

# Generate the dbt docs site into the shared volume so nginx can serve it at /dbt-docs/.
# Runs inside the app container (it has dbt + the prod profile + BQ creds via the env).
# Best-effort: a docs failure (e.g. BQ unreachable) must not fail the deploy.
echo "Generating dbt docs..."
docker exec olist-dagster sh -c '
  cd /app/p3_dbt_project/brazil_ecommerce
  # Catalog queries fail until the BQ datasets exist; index.html + manifest.json are
  # still written, so publish whatever was produced regardless of the exit code.
  dbt docs generate --profiles-dir . --target prod || true
  for f in index.html manifest.json catalog.json; do
    [ -f "target/$f" ] && cp "target/$f" /opt/dbt-docs/
  done
' && echo "dbt docs published to /dbt-docs/" || echo "WARN: dbt docs publish failed (deploy continues)."

echo "Started olist-dagster (internal) + dagster-proxy (public :3000, password-gated)."
echo "UI:        http://<VM-IP>:3000/"
echo "dbt docs:  http://<VM-IP>:3000/dbt-docs/"
echo "Logs:  docker logs -f olist-dagster"
