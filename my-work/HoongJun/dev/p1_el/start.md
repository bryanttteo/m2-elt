# START — Run the CSV → BigQuery Uploader

Get the web server running. Do **Prerequisites** once; after that it starts smoothly.

> This is the **p1_el** subproject. All commands run from the `p1_el/` folder (it has its own `pyproject.toml`).

---

## Prerequisites (one-time)

**1. Install `uv`**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS / Linux
```
Verify: `uv --version`

**2. Get the service-account key**
Place the shared key at `p1_el/secrets/`:
```
p1_el/secrets/sctp-team2-project2-elt-1853e88c8665.json
```
> Shared securely (password manager / encrypted), never via Git. It is gitignored.

**3. Create the BigQuery dataset** (one person, once)
```bash
bq mk --location=ASIA-SOUTHEAST1 raw_commerce
```

---

## Run the server

From the **`p1_el/` folder**:
```bash
# 1. install dependencies (creates .venv, fast)
uv sync

# 2. configure env (key path already correct in the example)
cd webapp
cp .env.example .env

# 3. start
uv run python app.py
```
Open **http://localhost:8080**

> `uv run` works from `webapp/` because uv finds the `pyproject.toml` in the parent `p1_el/`.

---

## Verify

- Page loads: **“CSV → BigQuery Uploader”**.
- Footer shows `Auth: shared SA key`.
- Drop a CSV → **Upload** → green success with row count.

```bash
curl http://localhost:8080/healthz
# {"status":"ok","project":"sctp-team2-project2-elt","dataset":"raw_commerce"}
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No pyproject.toml found` | You’re in the wrong folder. `cd` to `p1_el/` (or its `webapp/` child) before `uv sync` / `uv run`. |
| `uv: command not found` | Install uv (Prereq 1), restart terminal. |
| `service-account key not found` | Key not at `p1_el/secrets/...json`, or `.env` path wrong. See Prereq 2. |
| Footer says `Auth: ADC` | `.env` missing — run `cp .env.example .env` in `webapp/`. |
| `403 ... denied` on upload | SA missing `bigquery.dataEditor` / `bigquery.jobUser`. Ask team lead. |
| dataset not found | Run Prereq 3. |
| Port 8080 in use | `PORT=8090 uv run python app.py` |

Stop: **Ctrl+C**.