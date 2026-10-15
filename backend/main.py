from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.model import EnergyModel
from backend.schemas import PredictionRequest, PredictionResponse

model: EnergyModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    model = EnergyModel()          # load once at startup
    yield


app = FastAPI(title="Energy Consumption Predictor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # restrict to the frontend URL before deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.get("/model/info")
def model_info():
    b = model.bundle
    return {
        "model_name": b["model_name"],
        "features": b["features"],
        "metrics": b["metrics"],
        "feature_defaults": b["feature_defaults"],
        "feature_ranges": b["feature_ranges"],
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    prediction, warnings = model.predict(request)
    return PredictionResponse(
        predicted_energy_wh=prediction,
        model_name=model.bundle["model_name"],
        warnings=warnings,
    )