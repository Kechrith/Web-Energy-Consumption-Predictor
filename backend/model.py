from pathlib import Path

import joblib
import pandas as pd

from training.features import time_features

MODEL_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "energy_model.joblib"


class EnergyModel:
    def __init__(self, path: Path = MODEL_PATH):
        self.bundle = joblib.load(path)
        self.pipeline = self.bundle["pipeline"]
        self.features = self.bundle["features"]
        self.ranges = self.bundle["feature_ranges"]

    def predict(self, request) -> tuple[float, list[str]]:
        row = request.model_dump(exclude={"timestamp"})
        row.update(time_features(request.timestamp))

        X = pd.DataFrame([row])[self.features]   # enforce training column order
        prediction = max(0.0, float(self.pipeline.predict(X)[0]))

        warnings = [
            f"{col}={row[col]} is outside the training range {lo:.1f}–{hi:.1f}"
            for col, (lo, hi) in self.ranges.items()
            if not lo <= row[col] <= hi
        ]
        return round(prediction, 2), warnings