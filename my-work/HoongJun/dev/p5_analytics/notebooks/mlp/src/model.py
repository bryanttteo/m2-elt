"""Model factory + estimator pipeline + optional hyperparameter search.

Models are chosen on data characteristics (plan §A.5):
  logistic_regression : interpretable baseline (coefficients name the risky lanes)
  random_forest       : non-linear state x category interactions, mixed types
  hist_gbm            : strong tabular default, fast, native NaN handling
  xgboost             : usually best tabular; optional (skipped if not installed)

class imbalance (~8% late) is handled with class_weight where supported, else via
sample_weight computed in train() (see pipeline.py).
"""
from __future__ import annotations

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .features import build_preprocessor

# Models that accept class_weight='balanced' directly.
SUPPORTS_CLASS_WEIGHT = {"logistic_regression", "random_forest"}


def _make_estimator(name: str, params: dict, random_state: int):
    if name == "logistic_regression":
        return LogisticRegression(random_state=random_state, **params)
    if name == "random_forest":
        return RandomForestClassifier(random_state=random_state, **params)
    if name == "hist_gbm":
        return HistGradientBoostingClassifier(random_state=random_state, **params)
    if name == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "model.name=xgboost but xgboost is not installed. "
                "pip install xgboost, or pick hist_gbm."
            ) from e
        return XGBClassifier(
            random_state=random_state, eval_metric="logloss",
            tree_method="hist", **params,
        )
    raise ValueError(f"Unknown model {name!r}")


def build_model(cfg: dict) -> Pipeline:
    """Full sklearn Pipeline: preprocessor -> classifier (train/serve parity)."""
    name = cfg["model"]["name"]
    params = dict(cfg["model"]["params"].get(name, {}))
    rs = cfg["split"]["random_state"]
    estimator = _make_estimator(name, params, rs)
    return Pipeline([
        ("prep", build_preprocessor()),
        ("model", estimator),
    ])


def maybe_search(pipe: Pipeline, X, y, cfg: dict, sample_weight=None):
    """Run RandomizedSearchCV when search.enabled, else return the plain pipeline.

    Returns (fitted_estimator, best_params_or_None).
    """
    search_cfg = cfg["search"]
    fit_kw = {"model__sample_weight": sample_weight} if sample_weight is not None else {}

    if not search_cfg.get("enabled"):
        pipe.fit(X, y, **fit_kw)
        return pipe, None

    from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

    name = cfg["model"]["name"]
    space = search_cfg["spaces"].get(name, {})
    if not space:
        print(f"⚠️  No search space for {name}; fitting without search.")
        pipe.fit(X, y, **fit_kw)
        return pipe, None

    cv = StratifiedKFold(
        n_splits=search_cfg["cv_folds"], shuffle=True,
        random_state=cfg["split"]["random_state"],
    )
    search = RandomizedSearchCV(
        pipe, param_distributions=space, n_iter=search_cfg["n_iter"],
        scoring=search_cfg["scoring"], cv=cv,
        random_state=cfg["split"]["random_state"], n_jobs=-1, refit=True,
    )
    search.fit(X, y, **fit_kw)
    print(f"🔎 Best {search_cfg['scoring']}={search.best_score_:.4f} | {search.best_params_}")
    return search.best_estimator_, search.best_params_
