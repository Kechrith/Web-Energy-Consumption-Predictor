"""Data loading, synthetic demo generation, and series preparation.

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

# Profile parameters per site type: base load, daytime load, weekend factor, schedule hours.
_PROFILES = {
    "University":          dict(base=140, peak=380, weekend=0.45, start=7,  end=19, cooling=9.0,  seed=11),
    "Commercial building": dict(base=60,  peak=260, weekend=0.25, start=8,  end=19, cooling=6.5,  seed=23),
    "Factory":             dict(base=520, peak=880, weekend=0.70, start=6,  end=22, cooling=4.0,  seed=37),
    "Hotel":               dict(base=110, peak=210, weekend=1.10, start=17, end=23, cooling=7.5,  seed=41),
    "Household":           dict(base=0.35, peak=1.6, weekend=1.15, start=18, end=22, cooling=0.08, seed=53),
}


@st.cache_data(show_spinner=False)
def generate_demo_data(site_type: str = "University", days: int = 180) -> pd.DataFrame:
    """Realistic synthetic hourly meter data (DEMONSTRATION ONLY).

    Combines a weekly schedule, a daily occupancy curve, temperature-driven cooling load,
    slow seasonal drift, noise, and a handful of injected unusual events.
    """
    p = _PROFILES.get(site_type, _PROFILES["University"])
    rng = np.random.default_rng(p["seed"])
    end = pd.Timestamp.today().normalize() - pd.Timedelta(hours=1)
    idx = pd.date_range(end=end, periods=days * 24, freq="h")
    hour = idx.hour.to_numpy()
    dow = idx.dayofweek.to_numpy()
    doy = idx.dayofyear.to_numpy()
    n = len(idx)

    # Weather: tropical climate (Phnom Penh-like), hot season around April.
    seasonal_t = 2.2 * np.sin((doy - 30) / 365 * 2 * np.pi)
    daily_t = 3.8 * np.sin((hour - 9) / 24 * 2 * np.pi)
    temp = 28.0 + seasonal_t + daily_t + rng.normal(0, 0.8, n)
    humidity = np.clip(76 - 1.6 * daily_t + rng.normal(0, 4, n), 45, 98)

    # Occupancy curve: smooth ramp inside schedule hours.
    s, e = p["start"], p["end"]
    occ = 1 / (1 + np.exp(-(hour - s) * 1.6)) * 1 / (1 + np.exp((hour - e) * 1.6))
    if site_type == "Household":
        occ = 0.55 * np.exp(-((hour - 7) ** 2) / 3) + np.exp(-((hour - 20) ** 2) / 5)
    weekend = np.where(dow >= 5, p["weekend"], 1.0)
    if site_type == "Factory":
        weekend = np.where(dow == 6, 0.35, np.where(dow == 5, 0.75, 1.0))

    drift = 1 + 0.06 * np.sin(np.arange(n) / n * 2 * np.pi) + 0.04 * np.arange(n) / n
    cooling = p["cooling"] * np.clip(temp - 24, 0, None) * (0.4 + 0.6 * occ)
    load = (p["base"] + (p["peak"] - p["base"]) * occ * weekend) * drift + cooling
    load *= 1 + rng.normal(0, 0.045, n)

    # Injected unusual events (documented so the demo stays honest).
    def bump(day_offset: int, hours: range, factor: float) -> None:
        start = n - day_offset * 24
        for h in hours:
            if 0 <= start + h < n:
                load[start + h] *= factor

    bump(9, range(0, 7), 2.4)        # equipment left running overnight
    bump(23, range(10, 16), 1.65)    # unusual daytime spike
    bump(41, range(8, 20), 0.18)     # supply outage / meter fault
    bump(67, range(0, 24), 1.45)     # event day
    bump(118, range(13, 18), 1.8)    # chiller fault

    return pd.DataFrame({
        "timestamp": idx,
        "consumption_kwh": np.round(np.maximum(load, 0), 3),
        "temperature_c": np.round(temp, 1),
        "humidity_pct": np.round(humidity, 1),
    })


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
