# Meltano Raw CSV → BigQuery POC

Pulls Olist CSV files from a GCS bucket and loads them into BigQuery via Meltano.

```
GCS bucket  →  gsutil download  →  data/raw/*.csv  →  tap-csv  →  target-bigquery  →  BigQuery
```

## Prerequisites

- Conda env with **Python 3.11** (Singer/Meltano break on 3.12+).
- `gsutil` installed and authenticated.
- GCP service-account JSON with:
  - `roles/storage.objectViewer` on bucket `m2_olin_raw`
  - `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` on the project

## Install meltano in the conda env

Do NOT use pipx — it installs against a different Python and causes endless errors.

```bash
conda activate elt          # Python 3.11
pip install meltano
which meltano               # must point inside the conda env, not ~/.local/bin
```

## Configure `meltano.yml`

Key bit — pin `setuptools<80` in the loader's `pip_url` so `pkg_resources` is available:

```yaml
plugins:
  extractors:
    - name: tap-csv
      variant: meltanolabs
      pip_url: git+https://github.com/MeltanoLabs/tap-csv.git
      config:
        files:
          - { entity: customers, path: data/raw/olist_customers_dataset.csv, keys: [customer_id] }
          # ... 8 more

  loaders:
    - name: target-bigquery
      variant: z3z1ma
      pip_url: git+https://github.com/z3z1ma/target-bigquery.git setuptools<80
      config:
        project: sctp-team2-project2-elt
        dataset: olin_bronze_dev_jun
        method: batch_job
        location: US
        denormalized: true
        flattening_enabled: true
        flattening_max_depth: 1

jobs:
  - name: olin-pipeline
    tasks:
      - tap-csv target-bigquery
```

## Set credentials in `.env` (gitignored)

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/sa-key.json
```

## Run

```bash
# one-time
bq mk -d --location=US sctp-team2-project2-elt:olin_bronze_dev_jun
meltano install

# every time
make pipeline
```

The `Makefile` runs `gsutil cp` to pull the CSVs into `data/raw/`, then `meltano run`.

Verify:
```bash
bq ls sctp-team2-project2-elt:olin_bronze_dev_jun   # 9 tables
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'pkg_resources'` | `setuptools` not in plugin venv | Pin `setuptools<80` in the loader's `pip_url` (see config above), then `rm -rf .meltano/loaders/target-bigquery && meltano install` |
| `Utility 'extractor' is not known to Meltano` | `meltano` running on wrong Python (usually 3.14 via pipx) | `pipx uninstall meltano && rm -f ~/.local/bin/meltano && pip install meltano` inside the conda env |
| `MigrationError: Cannot upgrade the system database` | Stale system DB from older Meltano | `rm -rf .meltano/meltano.db .meltano/run .meltano/logs && meltano install` |
| `meltano install` fails for `tap-spreadsheets-anywhere` | Upstream `setup.py` is broken on `main` | Use `tap-csv` with a local `gsutil` pull (this project's approach) |
| `ModuleNotFoundError: No module named 'singer_sdk'` | Running tap directly from your shell venv | Use `meltano invoke ...` so it uses the plugin's own venv |
