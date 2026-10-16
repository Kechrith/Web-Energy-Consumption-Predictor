"""Anomaly detection.

Local method: robust seasonal z-score. "Expected" consumption for each period is the median
of the same weekday (and hour) in the surrounding weeks; deviations are scored with the
median absolute deviation (MAD), which is resistant to the anomalies themselves.

Isolation Forest and Autoencoder methods are requested from the FastAPI backend.

An anomaly is a *signal worth investigating*, not proof of a fault or energy waste.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

METHODS = {
    "Statistical threshold": {"local": True,
                              "help": "Robust z-score against the typical value for the same weekday/hour. Runs locally."},
    "Isolation Forest": {"local": False,
                         "help": "Tree-based outlier detection on multiple features. Requires the FastAPI backend."},
    "Autoencoder": {"local": False,
                    "help": "Neural reconstruction error. Requires the FastAPI backend and a trained model."},
}

SENSITIVITY = {  # label -> z-score threshold
    "Low (only extreme events)": 4.0,
    "Medium (recommended)": 3.0,
    "High (flag more periods)": 2.25,
}


def detect_statistical(series: pd.DataFrame, freq: str, threshold: float = 3.0, weeks: int = 3) -> pd.DataFrame:
    """Return the series with expected value, deviation, z-score, severity and anomaly flag."""
    y = series["y"].astype(float)
    season = 168 if freq == "hourly" else 7

    def _score(reference: pd.Series):
        shifts = [reference.shift(k * season) for k in range(-weeks, weeks + 1) if k != 0]
        exp = pd.concat(shifts, axis=1).median(axis=1, skipna=True)
        exp = exp.fillna(y.rolling(season, min_periods=1, center=True).median())
        res = y - exp
        mad = float(np.nanmedian(np.abs(res - np.nanmedian(res))))
        scale = 1.4826 * mad if mad > 0 else float(np.nanstd(res) or 1.0)
        return exp, res, res / scale

    # Pass 1 finds clear outliers; pass 2 excludes them from the reference so one spike
    # does not inflate the "expected" value of neighbouring weeks.
    _, _, z1 = _score(y)
    expected, resid, z = _score(y.where(z1.abs() <= threshold))

    out = pd.DataFrame({
        "timestamp": series.index,
        "observed": y.to_numpy(),
        "expected": expected.to_numpy(),
        "deviation": resid.to_numpy(),
        "deviation_pct": np.where(expected.to_numpy() > 0, resid.to_numpy() / expected.to_numpy() * 100, np.nan),
        "score": z.to_numpy(),
    })
    absz = out["score"].abs()
    out["is_anomaly"] = absz > threshold
    out["severity"] = np.select(
        [absz >= threshold + 3, absz >= threshold + 1.5, out["is_anomaly"]],
        ["High", "Medium", "Low"], default="",
    )
    out["direction"] = np.where(out["deviation"] >= 0, "Above expected", "Below expected")
    return out


def anomaly_table(result: pd.DataFrame) -> pd.DataFrame:
    a = result[result["is_anomaly"]].copy()
    order = {"High": 0, "Medium": 1, "Low": 2}
    a["_o"] = a["severity"].map(order)
    return a.sort_values(["_o", "timestamp"], ascending=[True, False]).drop(columns="_o")


def investigation_hint(row: pd.Series) -> str:
    if row["deviation"] >= 0:
        return "Check for equipment left running, scheduling changes, events, or HVAC faults."
    return "Check for outages, closures or holidays, missing meter readings, or communication faults."
