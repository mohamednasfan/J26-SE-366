"""Evaluation helpers for drug-disjoint (zero-shot) experiments."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from .metrics import classification_metrics, select_f1_threshold


def evaluate_zero_shot(
    model: Any,
    features: Any,
    labels: Any,
    drug_pairs: Iterable[tuple[str, str]],
    held_out_drugs: Iterable[str],
    threshold: float | None = None,
) -> dict[str, Any]:
    """Evaluate only pairs where at least one drug is held out.

    ``drug_pairs`` must align row-for-row with ``features`` and ``labels``.
    """
    held_out = {str(drug_id).upper() for drug_id in held_out_drugs}
    pairs = list(drug_pairs)
    mask = np.array(
        [
            str(first).upper() in held_out or str(second).upper() in held_out
            for first, second in pairs
        ],
        dtype=bool,
    )
    if not mask.any():
        raise ValueError("No evaluation pairs contain a held-out drug.")
    scores = np.asarray(model.predict_proba(np.asarray(features)[mask]))[:, 1]
    selected_threshold = (
        select_f1_threshold(np.asarray(labels)[mask], scores)
        if threshold is None
        else float(threshold)
    )
    return {
        "held_out_drugs": sorted(held_out),
        "pair_count": int(mask.sum()),
        "metrics": classification_metrics(
            np.asarray(labels)[mask], scores, selected_threshold
        ),
    }
