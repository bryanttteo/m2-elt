"""Evaluation — metrics chosen for an imbalanced, cost-asymmetric problem.

Primary: PR-AUC (average precision) + recall on the positive class. With ~8%
positives, ROC-AUC is optimistic, so it is reported only as a secondary number.
The decision threshold is tuned to a minimum recall (missing a late order is the
costly error) rather than left at 0.5.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.metrics import (
    average_precision_score, classification_report, confusion_matrix,
    f1_score, precision_recall_curve, precision_score, recall_score,
    roc_auc_score,
)


def tune_threshold(y_true, scores, cfg: dict) -> float:
    """Pick the threshold: highest precision s.t. recall >= min_recall, else default."""
    thr_cfg = cfg["threshold"]
    if not thr_cfg.get("tune_for_recall"):
        return float(thr_cfg["default"])
    prec, rec, thresholds = precision_recall_curve(y_true, scores)
    # precision_recall_curve returns one extra prec/rec point with no threshold.
    prec, rec = prec[:-1], rec[:-1]
    ok = rec >= thr_cfg["min_recall"]
    if not ok.any():
        print(f"⚠️  No threshold reaches recall>={thr_cfg['min_recall']}; using default.")
        return float(thr_cfg["default"])
    best = np.argmax(np.where(ok, prec, -1))
    return float(thresholds[best])


def evaluate(estimator, X_test, y_test, cfg: dict) -> dict:
    """Compute the metric suite at the tuned threshold; return a JSON-able dict."""
    scores = estimator.predict_proba(X_test)[:, 1]
    threshold = tune_threshold(y_test, scores, cfg)
    y_pred = (scores >= threshold).astype(int)

    metrics = {
        "target": cfg["target"],
        "model": cfg["model"]["name"],
        "n_test": int(len(y_test)),
        "positive_rate": float(np.mean(y_test)),
        "threshold": threshold,
        "pr_auc": float(average_precision_score(y_test, scores)),
        "roc_auc": float(roc_auc_score(y_test, scores)),
        "recall_pos": float(recall_score(y_test, y_pred)),
        "precision_pos": float(precision_score(y_test, y_pred, zero_division=0)),
        "f1_pos": float(f1_score(y_test, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    print("\n📊 Evaluation")
    for k in ["pr_auc", "roc_auc", "recall_pos", "precision_pos", "f1_pos", "threshold"]:
        print(f"   {k:14s}: {metrics[k]:.4f}")
    print("\n" + classification_report(y_test, y_pred, zero_division=0))
    return metrics


def plot_diagnostics(estimator, X_test, y_test, cfg: dict, out_dir: Path):
    """Save PR curve + confusion matrix. Returns list of written paths (or [])."""
    if not cfg["output"].get("plots"):
        return []
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import (ConfusionMatrixDisplay, PrecisionRecallDisplay)

    out_dir.mkdir(parents=True, exist_ok=True)
    scores = estimator.predict_proba(X_test)[:, 1]
    paths = []

    fig, ax = plt.subplots(figsize=(6, 5))
    PrecisionRecallDisplay.from_predictions(y_test, scores, ax=ax)
    ax.set_title(f"PR curve — {cfg['target']} / {cfg['model']['name']}")
    p = out_dir / "pr_curve.png"
    fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig); paths.append(p)

    thr = tune_threshold(y_test, scores, cfg)
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_predictions(
        y_test, (scores >= thr).astype(int), ax=ax, colorbar=False)
    ax.set_title(f"Confusion @ thr={thr:.2f}")
    p = out_dir / "confusion_matrix.png"
    fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig); paths.append(p)
    return paths


def feature_importance(estimator, top_n: int = 20):
    """Best-effort importance/coefficients aligned to transformed feature names."""
    try:
        names = estimator.named_steps["prep"].get_feature_names_out()
    except Exception:  # noqa: BLE001
        return None
    model = estimator.named_steps["model"]
    if hasattr(model, "feature_importances_"):
        vals = model.feature_importances_
    elif hasattr(model, "coef_"):
        vals = np.abs(model.coef_).ravel()
    else:
        return None
    import pandas as pd
    return (pd.DataFrame({"feature": names, "importance": vals})
            .sort_values("importance", ascending=False).head(top_n)
            .reset_index(drop=True))
