"""Rebuild artifacts/energy_model.joblib from the raw dataset.

Reproduces the final pipeline chosen in notebooks/full_process.ipynb.
Model comparison and tuning live in the notebook; this script only trains the selected model.

Run from the project root:
    python -m training.train
"""
import argparse
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from training.features import FEATURES

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "energydata_complete.csv"
MODEL_PATH = ROOT / "artifacts" / "energy_model.joblib"

TARGET = "Appliances"
MODEL_NAME = "HistGradientBoosting"
# Best settings from the validation search in the notebook (Step 6)
PARAMS = {"learning_rate": 0.05, "max_depth": 4, "min_samples_leaf": 50, "random_state": 42}


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Same time features as training.features.time_features()
    df["hour"] = df["date"].dt.hour
    df["dayofweek"] = df["date"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    return df


def split(df: pd.DataFrame):
    n = len(df)
    train_end, val_end = int(n * 0.70), int(n * 0.85)
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def make_model():
    pipe = Pipeline([("scaler", StandardScaler()), ("model", HistGradientBoostingRegressor(**PARAMS))])
    return TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=np.expm1)


def evaluate(y_true, y_pred) -> dict:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "R2": float(r2_score(y_true, y_pred)),
    }


def main(output: Path = MODEL_PATH):
    df = load_data(DATA_PATH)
    train, val, test = split(df)

    # 1. Fit on training data only to get honest train / validation / test scores
    model = make_model().fit(train[FEATURES], train[TARGET])
    metrics = {
        name: evaluate(part[TARGET], model.predict(part[FEATURES]))
        for name, part in [("train", train), ("validation", val), ("test", test)]
    }
    for name, m in metrics.items():
        print(f"{name:<10}  MAE {m['MAE']:7.3f}  RMSE {m['RMSE']:7.3f}  R2 {m['R2']:6.3f}")

    # 2. Retrain on train + validation for the final saved model
    trainval = pd.concat([train, val])
    final_model = make_model().fit(trainval[FEATURES], trainval[TARGET])

    bundle = {
        "pipeline": final_model,
        "features": FEATURES,
        "target": TARGET,
        "model_name": MODEL_NAME,
        "params": PARAMS,
        "metrics": metrics,
        "feature_defaults": trainval[FEATURES].median().to_dict(),
        "feature_ranges": {c: [float(trainval[c].min()), float(trainval[c].max())] for c in FEATURES},
        "trained_on": f"train + validation ({trainval['date'].min():%Y-%m-%d} to {trainval['date'].max():%Y-%m-%d})",
        "sklearn_version": sklearn.__version__,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output)
    print(f"Saved model to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and save the energy prediction model.")
    parser.add_argument("--output", type=Path, default=MODEL_PATH, help="where to save the .joblib file")
    main(parser.parse_args().output)
