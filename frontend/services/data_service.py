"""Data loading and series preparation.

Everything in this module runs locally. Swap `read_uploaded_file` / `prepare_series`
for backend calls (see services/api_client.py) once datasets are stored server-side.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from utils.validation import parse_datetimes

SITE_TYPES = ["University", "Commercial building", "Factory", "Hotel", "Household"]

# Repository root (one level above frontend/) and the UCI dataset used to train backend/ models.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UCI_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "energydata_complete.csv"


@st.cache_data(show_spinner=False)
def load_uci_dataset(path: str = str(UCI_DATA_PATH)) -> pd.DataFrame:
    """The project's UCI Appliances Energy dataset from data/raw/, with `appliances_kwh` added.

    `Appliances` is Wh per 10-minute reading; the analytics pages work in kWh.
    """
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df.insert(1, "appliances_kwh", df["Appliances"] / 1000)
    return df


def read_uploaded_file(upload) -> tuple[pd.DataFrame | None, str | None]:
    """Parse a CSV/Excel upload. Returns (dataframe, error_message)."""
    if upload is None:
        return None, "No file selected."
    name = upload.name.lower()
    data = upload.getvalue()
    if not data:
        return None, "The file is empty."
    try:
        if name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(data))
        elif name.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", encoding="latin-1")
        else:
            return None, "Unsupported file type. Upload a .csv or .xlsx file."
    except Exception as exc:  # pandas raises many parser-specific errors
        return None, f"The file could not be parsed ({type(exc).__name__}: {exc})."
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 2:
        return None, "The file needs at least two columns: a timestamp and a consumption value."
    return df, None


def prepare_series(df: pd.DataFrame, time_col: str, target_col: str,
                   weather_cols: list | None = None) -> tuple[pd.DataFrame, str]:
    """Return a regular time series indexed by timestamp with column `y` (+ weather) and its frequency.

    Hourly or finer data → hourly totals; anything else → daily totals.
    Gaps are interpolated in time; duplicate timestamps are averaged.
    """
    weather_cols = [c for c in (weather_cols or []) if c in df.columns and c not in (time_col, target_col)]
    data = pd.DataFrame({"timestamp": parse_datetimes(df[time_col]),
                         "y": pd.to_numeric(df[target_col], errors="coerce")})
    for c in weather_cols:
        data[c] = pd.to_numeric(df[c], errors="coerce")
    data = data.dropna(subset=["timestamp"]).sort_values("timestamp")
    if data.empty:
        return pd.DataFrame(columns=["y"]), "unknown"

    data = data.groupby("timestamp").mean()
    step = data.index.to_series().diff().median()
    freq = "hourly" if pd.notna(step) and step <= pd.Timedelta(hours=1, minutes=5) else "daily"
    rule = "h" if freq == "hourly" else "D"

    agg = {"y": "sum", **{c: "mean" for c in weather_cols}}
    if freq == "hourly" and step >= pd.Timedelta(minutes=55):
        out = data.resample(rule).mean()
    else:
        out = data.resample(rule).agg(agg)
        out.loc[data["y"].resample(rule).count() == 0, "y"] = np.nan
    out = out.interpolate(method="time", limit_direction="both")
    return out, freq


def to_daily(series: pd.DataFrame) -> pd.DataFrame:
    if series.empty:
        return series
    agg = {c: ("sum" if c == "y" else "mean") for c in series.columns}
    return series.resample("D").agg(agg)


def period_kpis(daily: pd.DataFrame, tariff: float) -> dict:
    """Headline numbers for a daily series (kWh)."""
    y = daily["y"]
    if y.empty:
        return {}
    peak_day = y.idxmax()
    return {
        "total": float(y.sum()),
        "avg": float(y.mean()),
        "peak": float(y.max()),
        "peak_date": peak_day,
        "cost": float(y.sum() * tariff),
        "days": int(len(y)),
    }


def previous_period(full_daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """The equal-length period immediately before [start, end]."""
    length = end - start + pd.Timedelta(days=1)
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - length + pd.Timedelta(days=1)
    return full_daily.loc[prev_start:prev_end]
