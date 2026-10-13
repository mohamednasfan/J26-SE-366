"""Logistic-regression training and inference utilities for DDI prediction."""

from __future__ import annotations

from typing import Any

from sklearn.linear_model import LogisticRegression


def build_model(random_state: int = 42, **overrides: Any) -> LogisticRegression:
    """Build the protocol's logistic-regression classifier."""
    parameters = {
        "solver": "saga",
        "max_iter": 3000,
        "random_state": random_state,
    }
    parameters.update(overrides)
    return LogisticRegression(**parameters)


def train(features: Any, labels: Any, **overrides: Any) -> LogisticRegression:
    """Fit and return a logistic-regression DDI classifier."""
    return build_model(**overrides).fit(features, labels)
