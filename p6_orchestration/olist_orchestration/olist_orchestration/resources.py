# Importing config first loads .env and sets GOOGLE_APPLICATION_CREDENTIALS etc.
# BEFORE prepare_if_dev() runs `dbt parse` (which needs the connection env vars).
from . import config  # noqa: F401  (side-effect: load env)

from dagster_dbt import DbtProject, DbtCliResource

# dbt project lives in p3_dbt_project/brazil_ecommerce (NOT p3_dbt_project itself —
# that was the previous path bug; there is no dbt_project.yml one level up).
dbt_project = DbtProject(project_dir=config.DBT_DIR)
dbt_project.prepare_if_dev()  # auto-runs `dbt parse` -> manifest in dev

# profiles.yml lives inside the project dir; point dbt at it explicitly so the
# resolution doesn't fall back to ~/.dbt.
dbt_resource = DbtCliResource(
    project_dir=dbt_project,
    profiles_dir=str(config.DBT_DIR),
)
