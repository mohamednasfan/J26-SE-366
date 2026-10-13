"""Random-forest training utility for DDI prediction."""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier


def build_model(random_state: int = 42, **overrides: Any) -> RandomForestClassifier:
    """Build a reproducible random-forest classifier."""
    parameters = {
        "n_estimators": 300,
        "n_jobs": -1,
        "random_state": random_state,
    }
    parameters.update(overrides)
    return RandomForestClassifier(**parameters)


def train(features: Any, labels: Any, **overrides: Any) -> RandomForestClassifier:
    """Fit and return a random-forest DDI classifier."""
    return build_model(**overrides).fit(features, labels)
