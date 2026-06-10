"""Olist ELT — Ops Portal backend.

Serves the static status page and a server-side health API so the browser
never hits CORS. Each target resolves to one of three states:

    green  — reachable and ready (HTTP 2xx/3xx, or 401 on basic-auth endpoints,
             or a RUNNING VM that answers)
    yellow — a deployment / startup is in progress (Cloud Run has a not-yet-ready
             revision, or the Dagster VM is PROVISIONING/STAGING/REPAIRING)
    red    — not pingable

Deployment + VM state come from the GCP Admin APIs using Application Default
Credentials. If those calls fail (no creds / no permission), we degrade
gracefully to plain ping (green/red only) and report the reason.
"""

import concurrent.futures as futures
import json
import os
import urllib.request
import urllib.error

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder=None)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("GCP_PROJECT", "sctp-team2-project2-elt")
REGION = os.environ.get("GCP_REGION", "us-central1")
ZONE = os.environ.get("GCP_ZONE", "us-central1-a")
TIMEOUT = float(os.environ.get("PING_TIMEOUT", "6"))

# Targets. Override the whole list with the TARGETS env var (JSON) if URLs change.
#   kind: "http"      -> ping `url`; optional `cloud_run` name enables yellow-on-deploy
#         "cloud_run" -> readiness + deploy state purely from the Run Admin API
#         "vm"        -> Compute instance status + ping
DEFAULT_TARGETS = [
    {"id": "dash",       "kind": "http", "url": os.environ.get("DASH_URL", ""),
     "health": "/", "cloud_run": "olist-dash"},
    {"id": "streamlit",  "kind": "http", "url": os.environ.get("STREAMLIT_URL", ""),
     "health": "/_stcore/health", "cloud_run": "olist-streamlit"},
    {"id": "wordcloud",  "kind": "http", "url": os.environ.get("WORDCLOUD_URL", ""),
     "health": "/_stcore/health", "cloud_run": "olist-wordcloud"},
    {"id": "superset",   "kind": "http", "url": os.environ.get("SUPERSET_URL", ""),
     "health": "/health", "cloud_run": "olist-superset"},
    {"id": "dagster",    "kind": "vm", "url": os.environ.get("DAGSTER_URL", ""),
     "health": "/", "instance": "olist-dagster", "ok_status": (200, 401)},
    {"id": "postgres",   "kind": "cloudsql", "instance": "sctp-m2-olist"},
]


def _targets():
    raw = os.environ.get("TARGETS")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return DEFAULT_TARGETS


# --- GCP auth (lazy, optional) --------------------------------------------
_session = {"token": None, "err": None, "loaded": False}


def _gcp_token():
    """Return an OAuth access token via ADC, or None (with a cached reason)."""
    if _session["loaded"]:
        return _session["token"]
    _session["loaded"] = True
    try:
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"]
        )
        creds.refresh(Request())
        _session["token"] = creds.token
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        _session["err"] = f"{type(exc).__name__}: {exc}"
    return _session["token"]


def _gcp_get(url):
    token = _gcp_token()
    if not token:
        return None
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


# --- probes ---------------------------------------------------------------
def _ping(url, ok_status=(200, 201, 202, 204, 301, 302, 303, 307, 308)):
    """Return (reachable: bool, code: int|None). One retry to absorb cold starts."""
    headers = {"User-Agent": "olist-ops-portal/1.0"}
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status in ok_status, resp.status
        except urllib.error.HTTPError as e:
            return e.code in ok_status, e.code
        except Exception:  # noqa: BLE001 - DNS/connect/timeout => retry once
            last = None
    return False, last


def _cloud_run_deploying(name):
    """True if the service has a created-but-not-yet-ready revision (deploy in
    progress). Returns None if the API is unavailable."""
    url = (f"https://run.googleapis.com/v2/projects/{PROJECT}"
           f"/locations/{REGION}/services/{name}")
    try:
        svc = _gcp_get(url)
    except Exception:  # noqa: BLE001
        return None
    if not svc:
        return None
    latest_created = svc.get("latestCreatedRevision")
    latest_ready = svc.get("latestReadyRevision")
    # Different create vs ready, or a Ready condition that's still reconciling.
    if latest_created and latest_created != latest_ready:
        return True
    for cond in svc.get("conditions", []):
        if cond.get("type") == "Ready" and cond.get("state") not in (
            "CONDITION_SUCCEEDED", "CONDITION_FAILED"
        ):
            return True
    return False


def _vm_status(name):
    """Return the Compute instance status string (RUNNING/PROVISIONING/...) or
    None if unavailable / not found."""
    url = (f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}"
           f"/zones/{ZONE}/instances/{name}")
    try:
        inst = _gcp_get(url)
    except urllib.error.HTTPError as e:
        return "TERMINATED" if e.code == 404 else None
    except Exception:  # noqa: BLE001
        return None
    return inst.get("status") if inst else None


YELLOW_VM = {"PROVISIONING", "STAGING", "REPAIRING", "STOPPING"}


def _resolve(t):
    """Resolve one target to {id, state, detail, code}."""
    tid = t["id"]
    kind = t["kind"]
    url = t.get("url", "")
    health = (url.rstrip("/") + t.get("health", "/")) if url else ""

    if kind == "cloudsql":
        # Reachability isn't pingable over HTTP; report deployment/op state only.
        return {"id": tid, "state": "green", "detail": "managed (see Cloud SQL)"}

    if kind == "vm":
        status = _vm_status(t.get("instance", ""))
        if status in YELLOW_VM:
            return {"id": tid, "state": "yellow", "detail": f"VM {status.lower()}"}
        if not url:
            return {"id": tid, "state": "gray", "detail": "URL not configured"}
        ok, code = _ping(health, ok_status=t.get("ok_status", (200, 401)))
        if ok:
            return {"id": tid, "state": "green", "detail": "running", "code": code}
        # Not answering: if VM isn't RUNNING it's the nightly teardown.
        if status and status != "RUNNING":
            return {"id": tid, "state": "red", "detail": f"VM {status.lower()}",
                    "code": code}
        return {"id": tid, "state": "red", "detail": "not pingable", "code": code}

    # kind == "http" (Cloud Run apps)
    if not url:
        return {"id": tid, "state": "gray", "detail": "URL not configured"}
    deploying = _cloud_run_deploying(t["cloud_run"]) if t.get("cloud_run") else None
    if deploying:
        return {"id": tid, "state": "yellow", "detail": "deployment in progress"}
    ok, code = _ping(health)
    if ok:
        return {"id": tid, "state": "green", "detail": "running", "code": code}
    return {"id": tid, "state": "red", "detail": "not pingable", "code": code}


@app.route("/api/status")
def status():
    targets = _targets()
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_resolve, targets))
    return jsonify({
        "services": results,
        "auth": "ok" if _gcp_token() else "degraded",
        "auth_error": _session.get("err"),
    })


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
