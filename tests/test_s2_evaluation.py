import numpy as np

from components.s2_ddi_prediction.evaluation.metrics import (
    classification_metrics,
    select_f1_threshold,
)
from components.s2_ddi_prediction.explainability.shap_explainer import (
    explain_linear_model,
)
from components.s2_ddi_prediction.models.logistic_regression import build_model


def test_metrics_and_threshold_selection():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.05, 0.2, 0.8, 0.95])

    threshold = select_f1_threshold(labels, scores)
    result = classification_metrics(labels, scores, threshold)

    assert 0.2 < threshold <= 0.8
    assert result["f1"] == 1.0
    assert result["roc_auc"] == 1.0
    assert result["pr_auc"] == 1.0
    assert result["confusion_matrix"] == [[2, 0], [0, 2]]


def test_linear_shap_reconstructs_model_logit():
    features = np.array([[0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
    labels = np.array([0, 1, 1])
    model = build_model(solver="liblinear").fit(features, labels)

    result = explain_linear_model(model, features, features[:1])

    assert len(result["values"]) == 1
    assert np.isclose(result["base_values"][0] + sum(result["values"][0]), result["logits"][0])
