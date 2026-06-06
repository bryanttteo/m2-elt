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
  -v "$PWD/.env.key:/secrets/sa.json:ro" \
  "$IMAGE" \
  dagster dev -h 0.0.0.0 -p 3000 -m olist_orchestration.definitions

# nginx Basic-Auth proxy — the only container published to public :3000.
docker rm -f dagster-proxy 2>/dev/null || true
docker run -d --name dagster-proxy --restart unless-stopped --network dagnet \
  -p 3000:3000 \
  -v "$PWD/nginx-dagster.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/dagster.htpasswd:/etc/nginx/.htpasswd:ro" \
  nginx:stable

echo "Started olist-dagster (internal) + dagster-proxy (public :3000, password-gated)."
echo "Logs:  docker logs -f olist-dagster"
