"""Consistent metrics for standard and zero-shot evaluation."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(
    y_true: np.ndarray, y_probability: np.ndarray, threshold: float = 0.5
) -> dict[str, float]:
    """Calculate the metrics used by every DDI model."""
    y_true = np.asarray(y_true)
    y_probability = np.asarray(y_probability)
    if y_true.ndim != 1 or y_probability.ndim != 1:
        raise ValueError("y_true and y_probability must be one-dimensional")
    if len(y_true) != len(y_probability):
        raise ValueError("y_true and y_probability must have equal lengths")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    y_pred = (y_probability >= threshold).astype(int)
    return {
        "auc_roc": float(roc_auc_score(y_true, y_probability)),
        "auc_pr": float(average_precision_score(y_true, y_probability)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
    }
