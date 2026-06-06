# Load env (and resolve the keyfile) before anything touches dbt/BigQuery.
from . import config  # noqa: F401

from dagster import (
    Definitions,
    define_asset_job,
    AssetSelection,
    ScheduleDefinition,
    DefaultScheduleStatus,
)
from dagster_dbt import build_dbt_asset_selection

from .assets import bronze_raw_commerce, dbt_models
from .resources import dbt_resource

# Select dbt models by the tags set in dbt_project.yml (tags: ['stage'/'gold_mart']).
stg_selection = build_dbt_asset_selection([dbt_models], dbt_select="tag:stage")
gold_selection = build_dbt_asset_selection([dbt_models], dbt_select="tag:gold_mart")

# Full refresh: bronze load -> all stg -> all gold (everything, in dependency order).
olist_full_refresh = define_asset_job("olist_full_refresh", selection=AssetSelection.all())
# Narrower jobs for iterating on just one dbt layer.
stg_only = define_asset_job("stg_only", selection=stg_selection)
gold_mart_only = define_asset_job("gold_mart_only", selection=gold_selection)

# Nightly full refresh (02:00 Asia/Singapore). The dagster-daemon (bundled into
# `dagster dev`, both locally and on the prod VM) fires this. default_status=RUNNING
# means it's armed on deploy without a manual toggle in the UI.
olist_nightly = ScheduleDefinition(
    name="olist_nightly",
    job=olist_full_refresh,
    cron_schedule="0 2 * * *",
    execution_timezone="Asia/Singapore",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=[bronze_raw_commerce, dbt_models],
    jobs=[olist_full_refresh, stg_only, gold_mart_only],
    schedules=[olist_nightly],
    resources={"dbt": dbt_resource},
)
