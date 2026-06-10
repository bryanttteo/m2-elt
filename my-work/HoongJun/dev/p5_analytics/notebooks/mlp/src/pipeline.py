"""End-to-end orchestration: load -> label -> features -> split -> train -> evaluate -> persist.

Importable as functions (used thin in mlp.ipynb) AND runnable as a script:

    python -m src.pipeline                          # uses config.yaml
    python -m src.pipeline --set model.name=random_forest --set search.enabled=true
    MLP_TARGET=repeat_purchase python -m src.pipeline
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

from . import evaluate as ev
from .config import load_config, resolve_path
from .features import engineer, split_X_y
from .ingest import load_data
from .labels import make_labels
from .model import SUPPORTS_CLASS_WEIGHT, build_model, maybe_search


def split_data(df: pd.DataFrame, cfg: dict):
    X, y = split_X_y(df)
    s = cfg["split"]
    return train_test_split(
        X, y, test_size=s["test_size"], random_state=s["random_state"],
        stratify=y if s.get("stratify") else None,
    )


def _sample_weight(cfg: dict, y_train):
    """For models without class_weight, balance via sample_weight (else None)."""
    if cfg["imbalance"]["strategy"] != "auto":
        return None
    if cfg["model"]["name"] in SUPPORTS_CLASS_WEIGHT:
        return None  # handled by class_weight='balanced' in the estimator params
    return compute_sample_weight(class_weight="balanced", y=y_train)


def train(X_train, y_train, cfg: dict):
    pipe = build_model(cfg)
    sw = _sample_weight(cfg, y_train)
    estimator, best_params = maybe_search(pipe, X_train, y_train, cfg, sample_weight=sw)
    return estimator, best_params


def persist(estimator, metrics: dict, cfg: dict, out_dir: Path, best_params=None):
    import joblib

    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / cfg["output"]["model_file"]
    joblib.dump(estimator, model_path)
    metrics = {**metrics, "best_params": best_params}
    with open(out_dir / cfg["output"]["metrics_file"], "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\n💾 Saved model -> {model_path}")
    print(f"💾 Saved metrics -> {out_dir / cfg['output']['metrics_file']}")


def run(cfg: dict) -> dict:
    """Run the full pipeline end-to-end and return the metrics dict."""
    print(f"\n{'='*70}\n🚀 MLP pipeline | target={cfg['target']} | model={cfg['model']['name']}\n{'='*70}")
    raw = load_data(cfg)
    labelled = make_labels(raw, cfg)
    feats = engineer(labelled)
    X_train, X_test, y_train, y_test = split_data(feats, cfg)
    print(f"🔀 Split: train={len(X_train):,}  test={len(X_test):,}")

    estimator, best_params = train(X_train, y_train, cfg)
    metrics = ev.evaluate(estimator, X_test, y_test, cfg)

    out_dir = resolve_path(cfg, cfg["output"]["dir"])
    ev.plot_diagnostics(estimator, X_test, y_test, cfg, out_dir)
    imp = ev.feature_importance(estimator)
    if imp is not None:
        print("\n🏆 Top features:\n", imp.head(12).to_string(index=False))
    persist(estimator, metrics, cfg, out_dir, best_params)
    return metrics


def main():
    ap = argparse.ArgumentParser(description="Olist MLP pipeline")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    ap.add_argument("--set", dest="overrides", action="append", default=[],
                    metavar="KEY=VALUE", help="override a config key (dotted)")
    args = ap.parse_args()
    cfg = load_config(args.config, args.overrides)
    run(cfg)


if __name__ == "__main__":
    main()
