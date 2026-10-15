"""SHAP explanation helpers with reconstruction checks."""

from __future__ import annotations

from typing import Any

import numpy as np


def explain_linear_model(model: Any, background: Any, features: Any) -> dict[str, Any]:
    """Explain a linear model and verify log-odds reconstruction."""
    try:
        import shap
    except ImportError as error:
        raise ImportError("Install shap to generate explanations.") from error
    background = np.asarray(background)
    features = np.asarray(features)
    if features.ndim != 2 or background.ndim != 2:
        raise ValueError("background and features must be two-dimensional.")
    if background.shape[1] != features.shape[1]:
        raise ValueError("background and features must have the same width.")
    explainer = shap.LinearExplainer(
        model,
        shap.maskers.Independent(background, max_samples=len(background)),
    )
    explanation = explainer(features)
    values = np.asarray(explanation.values)
    base_values = np.asarray(explanation.base_values)
    logits = np.asarray(model.decision_function(features))
    reconstructed = base_values.reshape(-1) + values.sum(axis=1)
    if not np.allclose(reconstructed, logits, atol=1e-6):
        raise RuntimeError("SHAP explanation reconstruction failed.")
    return {
        "base_values": base_values.reshape(-1).tolist(),
        "values": values.tolist(),
        "logits": logits.tolist(),
    }
