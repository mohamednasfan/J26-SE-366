from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/s2", tags=["Drug interactions"])


class PredictionRequest(BaseModel):
    drug1_id: str = Field(min_length=1, max_length=30)
    drug2_id: str = Field(min_length=1, max_length=30)
    top_k: int = Field(default=10, ge=1, le=30)
    mode: str = Field(default="standard", pattern="^(standard|cold_start)$")


@router.get("/drugs")
def search_drugs(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50)
):
    return {
        "results": request.app.state.ddi_predictor.search(q, limit)
    }


@router.post("/predict")
def predict_pair(body: PredictionRequest, request: Request):
    try:
        result = request.app.state.ddi_predictor.predict(
            body.drug1_id,
            body.drug2_id,
            body.top_k,
            body.mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    result["notice"] = (
        "Results are model estimates. A negative flag does not establish "
        "safety. SHAP features show model behaviour and should be verified "
        "with a qualified healthcare professional."
    )
    return result