from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from components.s2_ddi_prediction.api.predictor import DDIPredictor
from components.s2_ddi_prediction.api.routes import router as s2_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ddi_predictor = DDIPredictor()
    yield


app = FastAPI(
    title="MedSafeAI Research API",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(s2_router)


@app.get("/health")
def health():
    return {"status": "ok", "component": "s2_ddi_prediction"}


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")