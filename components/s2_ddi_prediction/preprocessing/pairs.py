"""Utilities for validating interaction pairs and creating negatives."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ("drug1", "drug2", "label")


def prepare_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    """Normalize pair columns and remove invalid or duplicate self-pairs."""
    missing = set(REQUIRED_COLUMNS) - set(pairs.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = pairs.loc[:, REQUIRED_COLUMNS].copy()
    result["drug1"] = result["drug1"].astype("string").str.strip()
    result["drug2"] = result["drug2"].astype("string").str.strip()
    result["label"] = pd.to_numeric(result["label"], errors="raise").astype("int8")

    if not result["label"].isin((0, 1)).all():
        raise ValueError("label must contain only 0 or 1")

    result = result.dropna()
    result = result[result["drug1"] != result["drug2"]]
    result["pair_key"] = result.apply(
        lambda row: tuple(sorted((row["drug1"], row["drug2"]))), axis=1
    )
    result = result.drop_duplicates("pair_key").drop(columns="pair_key")
    return result.reset_index(drop=True)


def sample_negative_pairs(
    positive_pairs: pd.DataFrame,
    drugs: Iterable[str] | None = None,
    ratio: float = 1.0,
    random_state: int = 42,
) -> pd.DataFrame:
    """Sample non-interacting pairs without overlapping known positives."""
    if ratio <= 0:
        raise ValueError("ratio must be greater than zero")

    positives = prepare_pairs(positive_pairs)
    positives = positives[positives["label"] == 1]
    drug_names = sorted(set(drugs or positives["drug1"]) | set(drugs or positives["drug2"]))
    if len(drug_names) < 2:
        raise ValueError("At least two drugs are required")

    forbidden = {
        tuple(sorted((row.drug1, row.drug2))) for row in positives.itertuples()
    }
    candidates = [
        (drug_names[i], drug_names[j])
        for i in range(len(drug_names))
        for j in range(i + 1, len(drug_names))
        if (drug_names[i], drug_names[j]) not in forbidden
    ]
    requested = int(np.ceil(len(positives) * ratio))
    if requested > len(candidates):
        raise ValueError("Not enough candidate negative pairs for the requested ratio")

    rng = np.random.default_rng(random_state)
    selected = rng.choice(len(candidates), size=requested, replace=False)
    negatives = pd.DataFrame(
        [(*candidates[index], 0) for index in selected],
        columns=["drug1", "drug2", "label"],
    )
    return pd.concat([positives, negatives], ignore_index=True)
