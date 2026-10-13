"""XGBoost training utility for DDI prediction."""

from __future__ import annotations

from typing import Any


def build_model(random_state: int = 42, **overrides: Any) -> Any:
    """Build an XGBoost classifier with conservative research defaults."""
    try:
        from xgboost import XGBClassifier
    except ImportError as error:
        raise ImportError("Install xgboost to use the XGBoost model.") from error
    parameters = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "logloss",
        "n_jobs": -1,
        "random_state": random_state,
    }
    parameters.update(overrides)
    return XGBClassifier(**parameters)


def train(features: Any, labels: Any, **overrides: Any) -> Any:
    """Fit and return an XGBoost DDI classifier."""
    return build_model(**overrides).fit(features, labels)
