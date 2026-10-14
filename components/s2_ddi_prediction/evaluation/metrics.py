"""Reusable evaluation metrics for binary DDI classifiers."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def select_f1_threshold(y_true: Any, scores: Any) -> float:
    """Return the score threshold that maximizes validation F1."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    if thresholds.size == 0:
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(
        precision[:-1] + recall[:-1], np.finfo(float).eps
    )
    best = np.flatnonzero(f1 == np.nanmax(f1))
    return float(thresholds[best[0]])


def classification_metrics(
    y_true: Any, scores: Any, threshold: float = 0.5
) -> dict[str, float | int | list[list[int]]]:
    """Compute thresholded and ranking metrics for binary predictions."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    predictions = (scores >= threshold).astype(int)
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "pr_auc": float(average_precision_score(y_true, scores)),
        "confusion_matrix": matrix.tolist(),
    }


def classification_report_dict(
    y_true: Any, scores: Any, threshold: float = 0.5
) -> dict[str, Any]:
    """Return the detailed sklearn report together with summary metrics."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    predictions = (scores >= threshold).astype(int)
    report = classification_report(
        y_true, predictions, labels=[0, 1], output_dict=True, zero_division=0
    )
    return {"metrics": classification_metrics(y_true, scores, threshold), "report": report}
