"""Configuration loading: YAML file <- env vars <- CLI ``--set`` overrides.

Precedence (lowest to highest): config.yaml  <  MLP_* env vars  <  --set k.v=x.
Keeping all knobs here means switching model/target/threshold is a config change,
never a code change (see readme-mlp.md "Configurability").
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import yaml

# mlp/ directory — all relative paths in the config resolve against this.
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = BASE_DIR / "config.yaml"

# Env vars that map onto specific config keys for quick one-offs.
ENV_MAP = {
    "MLP_TARGET": "target",
    "MLP_MODEL": "model.name",
    "GOOGLE_APPLICATION_CREDENTIALS": "bigquery.keyfile",
}


def _coerce(value: str) -> Any:
    """Turn a CLI/env string into a real Python type ('3' -> 3, 'true' -> True)."""
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _set_dotted(cfg: dict, dotted_key: str, value: Any) -> None:
    """Set cfg['a']['b'] = value from a dotted key 'a.b'."""
    keys = dotted_key.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def load_config(path: str | os.PathLike | None = None,
                overrides: list[str] | None = None) -> dict:
    """Load YAML, then apply env overrides, then ``--set key=value`` overrides."""
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path) as fh:
        cfg = yaml.safe_load(fh)

    for env_key, dotted in ENV_MAP.items():
        if os.environ.get(env_key):
            _set_dotted(cfg, dotted, _coerce(os.environ[env_key]))

    for item in overrides or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got: {item!r}")
        key, value = item.split("=", 1)
        _set_dotted(cfg, key.strip(), _coerce(value.strip()))

    cfg["_base_dir"] = str(BASE_DIR)
    return cfg


def resolve_path(cfg: dict, rel: str) -> Path:
    """Resolve a config path relative to the mlp/ directory."""
    p = Path(rel)
    return p if p.is_absolute() else (Path(cfg["_base_dir"]) / p)
