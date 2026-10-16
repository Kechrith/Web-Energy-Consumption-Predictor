"""Forecasting models and evaluation.

Local models (run in the browser session, real computations on the selected data):
  * Seasonal Naive      — repeats the last week (daily) or last week of hours (hourly).
  * Seasonal Average    — averages the same position over the last k weeks.
  * Linear Regression   — ridge regression on calendar features (+ weather in Model Lab).

Backend models (ARIMA, Prophet, Random Forest, XGBoost) are NOT simulated here —
they are requested from the FastAPI service via services/api_client.py.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

LOCAL_MODELS = {
    "Seasonal Naive": "Repeats the most recent weekly pattern. A strong, honest baseline every model should beat.",
    "Seasonal Average": "Averages the same weekday (and hour) over the last few weeks. Smoother than Seasonal Naive.",
    "Linear Regression": "Ridge regression on trend, weekday, hour-of-day and seasonal features.",
}
BACKEND_MODELS = {
    "ARIMA": "Classical autoregressive model. Requires the FastAPI backend.",
    "Prophet": "Additive trend + seasonality model. Requires the FastAPI backend.",
    "Random Forest": "Tree ensemble on lag and calendar features. Requires the FastAPI backend.",
    "XGBoost": "Gradient-boosted trees on lag and calendar features. Requires the FastAPI backend.",
}
ALL_MODELS = list(LOCAL_MODELS) + list(BACKEND_MODELS)

DEFAULT_PARAMS = {
    "Seasonal Naive": {},
    "Seasonal Average": {"weeks": 4},
    "Linear Regression": {"alpha": 1.0, "use_weather": False},
    "ARIMA": {"p": 2, "d": 1, "q": 2},
    "Prophet": {"changepoint_prior_scale": 0.05, "seasonality_mode": "additive"},
    "Random Forest": {"n_estimators": 300, "max_depth": 12},
    "XGBoost": {"n_estimators": 500, "learning_rate": 0.05, "max_depth": 6},
}


def season_length(freq: str) -> int:
    return 168 if freq == "hourly" else 7


def periods_per_day(freq: str) -> int:
    return 24 if freq == "hourly" else 1


def future_index(last: pd.Timestamp, steps: int, freq: str) -> pd.DatetimeIndex:
    offset = pd.Timedelta(hours=1) if freq == "hourly" else pd.Timedelta(days=1)
    return pd.date_range(last + offset, periods=steps, freq="h" if freq == "hourly" else "D")


# ---------------- Metrics ----------------
def regression_metrics(actual, predicted) -> dict:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(p))
    a, p = a[mask], p[mask]
    if len(a) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "MAPE": np.nan, "R2": np.nan}
    err = a - p
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    # MAPE is undefined / misleading when actual values are at or near zero.
    mape = float(np.mean(np.abs(err / a)) * 100) if np.all(np.abs(a) > 0.01 * max(np.mean(np.abs(a)), 1e-9)) else np.nan
    ss_tot = float(np.sum((a - a.mean()) ** 2))
    r2 = float(1 - np.sum(err ** 2) / ss_tot) if ss_tot > 0 else np.nan
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape, "R2": r2}


# ---------------- Linear model helpers ----------------
def _calendar_features(index: pd.DatetimeIndex, freq: str, t0: pd.Timestamp) -> pd.DataFrame:
    f = pd.DataFrame(index=index)
    f["trend"] = (index - t0) / pd.Timedelta(days=1)
    for d in range(1, 7):
        f[f"dow_{d}"] = (index.dayofweek == d).astype(float)
    if freq == "hourly":
        weekend = (index.dayofweek >= 5).astype(float)
        for h in range(1, 24):
            is_h = (index.hour == h).astype(float)
            f[f"hour_{h}"] = is_h
            f[f"hour_{h}_we"] = is_h * weekend
    doy = index.dayofyear.to_numpy()
    f["annual_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["annual_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return f


def _feature_group(name: str) -> str:
    if name == "trend":
        return "Long-term trend"
    if name.startswith("dow_"):
        return "Day of week"
    if name.endswith("_we"):
        return "Weekend hour pattern"
    if name.startswith("hour_"):
        return "Hour of day"
    if name.startswith("annual"):
        return "Annual season"
    return name  # weather column names


def _fit_ridge(X: pd.DataFrame, y: np.ndarray, alpha: float) -> dict:
    mu, sd = X.mean(), X.std().replace(0, 1)
    Z = ((X - mu) / sd).to_numpy()
    yc = y - y.mean()
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ yc)
    return {"mu": mu, "sd": sd, "w": w, "b": y.mean(), "cols": list(X.columns)}


def _predict_ridge(model: dict, X: pd.DataFrame) -> np.ndarray:
    Z = ((X[model["cols"]] - model["mu"]) / model["sd"]).to_numpy()
    return Z @ model["w"] + model["b"]


def _importance(model: dict) -> pd.DataFrame:
    # Standardised coefficients: |w| reflects each feature's effect per 1 std change.
    imp = pd.DataFrame({"feature": model["cols"], "weight": np.abs(model["w"])})
    imp["group"] = imp["feature"].map(_feature_group)
    out = imp.groupby("group", as_index=False)["weight"].sum()
    out["importance"] = out["weight"] / out["weight"].sum()
    return out.sort_values("importance", ascending=False)[["group", "importance"]].rename(columns={"group": "feature"})


# ---------------- Fit / predict ----------------
def fit_predict(model: str, train: pd.DataFrame, target_index: pd.DatetimeIndex, freq: str,
                params: dict | None = None, exog_future: pd.DataFrame | None = None):
    """Fit `model` on `train` (column `y`) and predict for `target_index` (which follows `train`).

    Returns (predictions ndarray, feature-importance DataFrame or None).
    """
    if model not in LOCAL_MODELS:
        raise ValueError(f"'{model}' runs on the FastAPI backend, not locally.")
    params = {**DEFAULT_PARAMS.get(model, {}), **(params or {})}
    y = train["y"].to_numpy(dtype=float)
    s = season_length(freq)
    steps = len(target_index)
    if len(y) < s:
        raise ValueError("Not enough history for this model (need at least one full week).")

    if model == "Seasonal Naive":
        last = y[-s:]
        return np.array([last[i % s] for i in range(steps)]), None

    if model == "Seasonal Average":
        k = max(1, min(int(params["weeks"]), len(y) // s))
        block = y[-k * s:].reshape(k, s).mean(axis=0)
        return np.array([block[i % s] for i in range(steps)]), None

    # Linear Regression
    t0 = train.index[0]
    X = _calendar_features(train.index, freq, t0)
    Xf = _calendar_features(target_index, freq, t0)
    weather = [c for c in train.columns if c != "y"] if params.get("use_weather") else []
    if weather and exog_future is not None:
        X = X.join(train[weather])
        Xf = Xf.join(exog_future[weather])
    fitted = _fit_ridge(X, y, float(params["alpha"]))
    return np.maximum(_predict_ridge(fitted, Xf), 0), _importance(fitted)


def run_forecast(series: pd.DataFrame, freq: str, model: str, horizon_days: int,
                 params: dict | None = None, interval: float | None = 0.9) -> dict:
    """Backtest on the most recent window, then forecast `horizon_days` ahead.

    Prediction intervals are empirical: the chosen quantile of absolute backtest errors.
    """
    data = series[["y"]].dropna()
    steps = horizon_days * periods_per_day(freq)
    s = season_length(freq)
    holdout = int(min(steps, max(len(data) - 2 * s, s)))
    if len(data) < 2 * s + 1:
        raise ValueError("At least two weeks of history are required to forecast.")

    t_start = time.perf_counter()
    train, test = data.iloc[:-holdout], data.iloc[-holdout:]
    bt_pred, _ = fit_predict(model, train, test.index, freq, params)
    backtest = pd.DataFrame({"timestamp": test.index, "actual": test["y"].to_numpy(), "predicted": bt_pred})
    metrics = regression_metrics(backtest["actual"], backtest["predicted"])

    idx = future_index(data.index[-1], steps, freq)
    pred, importance = fit_predict(model, data, idx, freq, params)
    fc = pd.DataFrame({"timestamp": idx, "forecast": pred})
    if interval:
        q = float(np.quantile(np.abs(backtest["actual"] - backtest["predicted"]), interval))
        fc["lower"] = np.maximum(pred - q, 0)
        fc["upper"] = pred + q
    return {
        "model": model, "freq": freq, "horizon_days": horizon_days, "interval": interval,
        "forecast": fc, "backtest": backtest, "metrics": metrics, "importance": importance,
        "duration_s": time.perf_counter() - t_start, "created": pd.Timestamp.now(),
        "source": "local",
    }


def chronological_split(n: int, train_pct: int, val_pct: int) -> tuple[slice, slice, slice]:
    """Ordered train/validation/test slices — no shuffling, so no look-ahead leakage."""
    n_train = int(n * train_pct / 100)
    n_val = int(n * val_pct / 100)
    return slice(0, n_train), slice(n_train, n_train + n_val), slice(n_train + n_val, n)


def evaluate_local_model(series: pd.DataFrame, freq: str, model: str, params: dict,
                         train_pct: int, val_pct: int) -> dict:
    """Train on the train split, score on validation; retrain on train+val, score on test."""
    t_start = time.perf_counter()
    data = series.dropna(subset=["y"])
    tr, va, te = chronological_split(len(data), train_pct, val_pct)
    train, val, test = data.iloc[tr], data.iloc[va], data.iloc[te]
    if len(test) == 0 or len(val) == 0:
        raise ValueError("Validation and test splits must not be empty.")
    exog = [c for c in data.columns if c != "y"]

    val_pred, _ = fit_predict(model, train, val.index, freq, params, exog_future=val[exog])
    trval = data.iloc[: te.start]
    test_pred, importance = fit_predict(model, trval, test.index, freq, params, exog_future=test[exog])
    return {
        "model": model, "params": params, "status": "Completed", "source": "local",
        "val_metrics": regression_metrics(val["y"], val_pred),
        "test_metrics": regression_metrics(test["y"], test_pred),
        "test_frame": pd.DataFrame({"timestamp": test.index, "actual": test["y"].to_numpy(), "predicted": test_pred}),
        "importance": importance,
        "duration_s": time.perf_counter() - t_start,
        "split": {"train": (train.index[0], train.index[-1]), "val": (val.index[0], val.index[-1]),
                  "test": (test.index[0], test.index[-1])},
    }
