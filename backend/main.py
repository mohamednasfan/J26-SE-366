"""FastAPI entry point for DDI prediction.

The service deliberately reports model availability instead of returning a
success-shaped fallback when no trained model has been configured.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from components.s2_ddi_prediction.features.morgan import pair_fingerprint


class PredictionRequest(BaseModel):
    drug1_smiles: str = Field(min_length=1)
    drug2_smiles: str = Field(min_length=1)


class PredictionResponse(BaseModel):
    available: bool
    probability: float | None = None
    message: str


app = FastAPI(title="DDI Prediction API", version="0.1.0")
MODEL_PATH = Path(os.getenv("DDI_MODEL_PATH", "models/logistic_regression_model.pkl"))


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "model_configured": MODEL_PATH.exists()}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"No trained model found at {MODEL_PATH}. Train a model first.",
        )

    try:
        import joblib

        model = joblib.load(MODEL_PATH)
        features = pair_fingerprint(request.drug1_smiles, request.drug2_smiles)
        probability = float(model.predict_proba(features.reshape(1, -1))[0, 1])
    except (ImportError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PredictionResponse(
        available=True,
        probability=probability,
        message="Prediction generated successfully.",
    )
