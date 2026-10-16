# S2: Drug-Drug Interaction Prediction

S2 is a research prototype for predicting whether a pair of supported drugs is
associated with an interaction in the supplied dataset. It is not a clinical
decision tool.

## API

From the repository root:

```powershell
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/` in a browser to use the mobile-friendly demo.
It provides drug search, two-drug selection, prediction status, model score,
decision threshold, and a compact explanation view suitable for a viva.

Endpoints:

- `GET /api/s2/drugs?q=metformin`
- `POST /api/s2/predict` with `{"drug1_id": "DB00331", "drug2_id": "DB00945"}`

The web application uses the cold-start Random Forest mode, which was trained
for the one-unseen-drug protocol and uses its own validation-selected
threshold. Direct API requests default to the standard Random Forest and can
select cold start explicitly with `"mode": "cold_start"`. A negative flag does
not establish that a pair is safe.

## Reproducible evaluation utilities

- `evaluation/metrics.py` computes accuracy, precision, recall, F1, ROC-AUC,
  PR-AUC, and confusion matrices.
- `evaluation/zero_shot.py` evaluates pairs containing held-out drugs.
- `models/` contains builders for Logistic Regression, Random Forest, and
  XGBoost classifiers.
- `explainability/shap_explainer.py` verifies that SHAP values reconstruct the
  model log-odds.

The stored experiment uses 2048-bit Morgan fingerprints and pair features
formed from the fingerprint sum and absolute difference. Existing generated
datasets and model artifacts are intentionally not committed automatically;
their provenance and limitations are recorded under `data/audit/`.

## Limitations

The negative class consists of sampled pairs absent from the supplied positive
datasets, not confirmed clinical non-interactions. Dataset completeness,
original download history, clinical correctness of exploratory text features,
uncertainty under shared-drug dependence, and repeated-seed stability require
additional research before clinical or production use.
