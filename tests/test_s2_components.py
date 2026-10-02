import numpy as np
import pandas as pd
import pytest

from components.s2_ddi_prediction.evaluation.metrics import classification_metrics
from components.s2_ddi_prediction.features.morgan import pair_fingerprint
from components.s2_ddi_prediction.preprocessing.pairs import (
    prepare_pairs,
    sample_negative_pairs,
)


def test_prepare_pairs_normalizes_and_deduplicates():
    pairs = pd.DataFrame(
        [
            {"drug1": " aspirin ", "drug2": "warfarin", "label": 1},
            {"drug1": "warfarin", "drug2": "aspirin", "label": 1},
            {"drug1": "aspirin", "drug2": "aspirin", "label": 1},
        ]
    )

    result = prepare_pairs(pairs)

    assert len(result) == 1
    assert result.loc[0, "drug1"] == "aspirin"


def test_negative_sampling_is_reproducible_and_disjoint():
    positives = pd.DataFrame(
        [{"drug1": "a", "drug2": "b", "label": 1}]
    )

    first = sample_negative_pairs(positives, drugs=["a", "b", "c"], random_state=7)
    second = sample_negative_pairs(positives, drugs=["a", "b", "c"], random_state=7)

    pd.testing.assert_frame_equal(first, second)
    assert not ((first["drug1"] == "a") & (first["drug2"] == "b") & (first["label"] == 0)).any()


def test_pair_fingerprint_has_expected_shape():
    features = pair_fingerprint("CCO", "CC(=O)O", n_bits=32)
    assert features.shape == (64,)
    assert set(np.unique(features)).issubset({0.0, 1.0})


def test_metrics_validate_lengths():
    with pytest.raises(ValueError, match="equal lengths"):
        classification_metrics(np.array([0, 1]), np.array([0.2]))
