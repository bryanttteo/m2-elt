import csv as csvmod
import subprocess
from pathlib import Path

from dagster import multi_asset, AssetOut, AssetExecutionContext, AssetKey, Output, MetadataValue
from dagster_dbt import dbt_assets, DbtCliResource, DagsterDbtTranslator

from . import config
from .resources import dbt_project

# Env-suffixed medallion asset-key prefixes, driven by OLIST_ENV, so dev/prod/jun
# runs show as distinct assets: olist_<layer>_<env>/. The bronze multi_asset and the
# dbt source assets share BRONZE_KEY_PREFIX so bronze -> stg stays wired within a run.
ENV = config.OLIST_ENV
BRONZE_KEY_PREFIX = f"olist_bronze_{ENV}"


class OlistDbtTranslator(DagsterDbtTranslator):
    """Key assets by medallion layer + env: olist_bronze_<env>/<table>,
    olist_stage_<env>/<model>, olist_gold_mart_<env>/<model>. (dagster-dbt's default
    would prefix with the raw dataset name `brazil_ecommerce_<env>` — we use the
    consistent olist_<layer>_<env> form instead.)"""

    def get_asset_key(self, dbt_resource_props):
        resource_type = dbt_resource_props["resource_type"]
        name = dbt_resource_props["name"]
        if resource_type == "source":
            return AssetKey([BRONZE_KEY_PREFIX, name])
        tags = dbt_resource_props.get("tags") or []
        if "stage" in tags:
            return AssetKey([f"olist_stage_{ENV}", name])
        if "gold_mart" in tags:
            return AssetKey([f"olist_gold_mart_{ENV}", name])
        return AssetKey([name])


def _csv_record_count(path: Path) -> int:
    """Accurate record count: excludes header, handles quoted multiline fields
    (order_reviews comments contain embedded newlines, so `wc -l` overcounts)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return max(sum(1 for _ in csvmod.reader(f)) - 1, 0)


def _bq_client():
    """A BigQuery client using GOOGLE_APPLICATION_CREDENTIALS, or None if unavailable."""
    try:
        from google.cloud import bigquery
    except Exception:
        return None
    return bigquery.Client(project=config.GCP_PROJECT, location=config.BQ_LOCATION)


def _csv_header(csv_path: Path) -> list:
    """Column names from the CSV header, with the UTF-8 BOM stripped (utf-8-sig)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return next(csvmod.reader(f))


def _is_all_text(csv_path: Path) -> bool:
    """True when the first data row has no numeric value. BigQuery autodetect then
    can't distinguish the header row from data and falls back to string_field_N
    names — so we must name columns explicitly (e.g. product_category_name_translation)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        r = csvmod.reader(f)
        next(r, None)            # skip header
        row = next(r, None)      # first data row
    if not row:
        return False

    def _numeric(v: str) -> bool:
        try:
            float(v)
            return True
        except ValueError:
            return False

    return not any(_numeric(v) for v in row)


def _load_csv_to_bq(client, table: str, csv_path: Path):
    """Load one CSV into bronze.<table>, replacing the table.

    Typed columns -> autodetect. All-text files -> explicit STRING schema named
    from the (BOM-stripped) header, so the manual and Meltano load paths agree on
    column names instead of one producing string_field_0/1."""
    from google.cloud import bigquery

    dataset_ref = f"{config.GCP_PROJECT}.{config.BQ_BRONZE_DATASET}"
    ds = bigquery.Dataset(dataset_ref)
    ds.location = config.BQ_LOCATION
    client.create_dataset(ds, exists_ok=True)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        encoding="UTF-8",
        # order_reviews comments contain embedded newlines inside quoted fields.
        allow_quoted_newlines=True,
    )
    if _is_all_text(csv_path):
        job_config.schema = [
            bigquery.SchemaField(name, "STRING") for name in _csv_header(csv_path)
        ]
    else:
        job_config.autodetect = True

    table_id = f"{dataset_ref}.{table}"
    with open(csv_path, "rb") as f:
        client.load_table_from_file(
            f, table_id, job_config=job_config, location=config.BQ_LOCATION
        ).result()


def _bq_row_counts(client) -> dict:
    """{table: COUNT(*)} from bronze; 0 if a table is missing."""
    counts = {}
    for t in config.BRONZE_TABLES:
        try:
            q = f"SELECT COUNT(*) AS c FROM `{config.GCP_PROJECT}.{config.BQ_BRONZE_DATASET}.{t}`"
            counts[t] = list(client.query(q, location=config.BQ_LOCATION).result())[0].c
        except Exception:
            counts[t] = 0
    return counts


@multi_asset(
    outs={t: AssetOut(key=[BRONZE_KEY_PREFIX, t]) for t in config.BRONZE_TABLES},
    compute_kind="bigquery",
)
def bronze_raw_commerce(context: AssetExecutionContext):
    """Load all Olist CSVs into the BigQuery bronze dataset, then verify every
    CSV's record count landed in its table.

    Two load paths (BRONZE_LOAD_METHOD):
      - "manual"  (default): load datasets/*.csv straight into BQ via load jobs.
      - "meltano": run the tap-csv -> target-bigquery pipeline in p1_el/meltano-raw-csv.
    Both land in the SAME bronze _raw tables (olist_*_raw)."""
    method = config.BRONZE_LOAD_METHOD
    client = _bq_client()

    # 1) run the load
    if method == "meltano":
        context.log.info(f"Loading bronze via Meltano ({config.MELTANO_DIR})")
        subprocess.run(
            ["meltano", f"--environment={config.OLIST_ENV}", "run", "tap-csv", "target-bigquery"],
            cwd=config.MELTANO_DIR, check=True,
        )
    else:
        if client is None:
            raise RuntimeError(
                "google-cloud-bigquery is required for the manual load path. "
                "pip install google-cloud-bigquery, or set BRONZE_LOAD_METHOD=meltano."
            )
        context.log.info(f"Loading bronze manually from {config.OLIST_DATA_DIR}")
        for t in config.BRONZE_TABLES:
            csv_path = config.OLIST_DATA_DIR / config.CSV_FILES[t]
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing source CSV: {csv_path}")
            _load_csv_to_bq(client, t, csv_path)
            context.log.info(f"  loaded {t} <- {csv_path.name}")

    # 2) verify CSV -> bronze row counts
    bq = _bq_row_counts(client) if client is not None else None
    shortfalls = []
    context.log.info("=== Bronze load verification (CSV records vs BigQuery rows) ===")
    for t in config.BRONZE_TABLES:
        csv_path = config.OLIST_DATA_DIR / config.CSV_FILES[t]
        csv_rows = _csv_record_count(csv_path) if csv_path.exists() else None
        meta = {"csv_records": MetadataValue.int(csv_rows or 0)}

        if bq is not None:
            bq_rows = bq.get(t, 0)
            loaded = csv_rows is not None and bq_rows >= csv_rows
            exact = csv_rows is not None and bq_rows == csv_rows
            mark = "✅ exact" if exact else ("⚠️ appended (dupes)" if loaded else "❌ MISSING ROWS")
            meta.update({
                "bq_rows": MetadataValue.int(bq_rows),
                "status": MetadataValue.text(mark),
            })
            context.log.info(f"  {mark:22s} {t:38s} csv={csv_rows}  bq={bq_rows}")
            if not loaded:
                shortfalls.append(f"{t} (csv={csv_rows}, bq={bq_rows})")
        else:
            context.log.info(f"  {t:38s} csv={csv_rows}  (BQ check skipped)")

        yield Output(None, output_name=t, metadata=meta)

    if shortfalls:
        context.log.error(
            "Incomplete load — bronze has fewer rows than the source CSV for: "
            + ", ".join(shortfalls)
        )
    elif bq is not None:
        context.log.info("All bronze tables contain at least the full CSV record count. ✅")


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=OlistDbtTranslator())
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
