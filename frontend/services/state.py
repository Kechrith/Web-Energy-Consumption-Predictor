"""Session-state management for projects, datasets, settings, and results.

Everything here lives in `st.session_state` only — it is lost when the browser
session ends. Replace these helpers with `api_client` calls to persist on the backend.
"""

from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
import streamlit as st

from services.data_service import prepare_series, to_daily

DEFAULT_SETTINGS = {
    "workspace_name": "RUPP Energy Lab",
    "unit": "kWh",
    "default_horizon": 7,
    "default_model": "Seasonal Naive",
    "tariff": 0.18,
    "currency": "USD",
    "api_url": "http://localhost:8000",
    "api_timeout": 5,
    "confirm_delete": True,
    "keep_raw_upload": True,
    "notify_anomalies": True,
    "notify_training": True,
    "notify_email": "",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def init_state() -> None:
    ss = st.session_state
    if "settings" not in ss:
        ss.settings = dict(DEFAULT_SETTINGS)
    ss.setdefault("projects", {})
    ss.setdefault("datasets", {})
    ss.setdefault("active_project_id", None)
    ss.setdefault("forecasts", {})      # project_id -> last forecast result dict
    ss.setdefault("experiments", {})    # project_id -> list of experiment dicts
    ss.setdefault("anomaly_runs", {})   # project_id -> last anomaly result dict
    ss.setdefault("reviewed_anomalies", set())
    ss.setdefault("_prepared", {})


# ---------------- Projects ----------------
def create_project(name: str, site_type: str, description: str = "") -> str:
    pid = _new_id("prj")
    now = pd.Timestamp.now()
    st.session_state.projects[pid] = {
        "id": pid, "name": name.strip(), "site_type": site_type, "description": description.strip(),
        "status": "Active", "created": now, "last_activity": now, "active_dataset_id": None,
    }
    return pid


def delete_project(pid: str) -> None:
    ss = st.session_state
    for did in [d for d, ds in ss.datasets.items() if ds["project_id"] == pid]:
        ss.datasets.pop(did, None)
    ss.projects.pop(pid, None)
    for store in (ss.forecasts, ss.experiments, ss.anomaly_runs):
        store.pop(pid, None)
    if ss.get("active_project_id") == pid:
        ss.active_project_id = next(iter(ss.projects), None)


def active_project() -> dict | None:
    ss = st.session_state
    return ss.projects.get(ss.get("active_project_id"))


def touch(pid: str | None = None) -> None:
    pid = pid or st.session_state.get("active_project_id")
    if pid in st.session_state.projects:
        st.session_state.projects[pid]["last_activity"] = pd.Timestamp.now()


def name_taken(name: str, exclude: str | None = None) -> bool:
    key = name.strip().lower()
    return any(p["name"].lower() == key and p["id"] != exclude for p in st.session_state.projects.values())


# ---------------- Datasets ----------------
def project_datasets(pid: str | None) -> list[dict]:
    return [d for d in st.session_state.datasets.values() if d["project_id"] == pid]


def add_dataset(pid: str, name: str, df: pd.DataFrame, time_col: str, target_col: str,
                weather_cols: list, file_name: str) -> str:
    did = _new_id("ds")
    st.session_state.datasets[did] = {
        "id": did, "name": name.strip(), "project_id": pid, "source": "upload", "df": df,
        "time_col": time_col, "target_col": target_col, "weather_cols": list(weather_cols),
        "created": pd.Timestamp.now(), "file_name": file_name,
    }
    st.session_state.projects[pid]["active_dataset_id"] = did
    touch(pid)
    return did


def delete_dataset(did: str) -> None:
    ss = st.session_state
    ds = ss.datasets.pop(did, None)
    if ds:
        proj = ss.projects.get(ds["project_id"])
        if proj and proj["active_dataset_id"] == did:
            remaining = project_datasets(proj["id"])
            proj["active_dataset_id"] = remaining[0]["id"] if remaining else None
    invalidate_cache(did)


def invalidate_cache(did: str | None = None) -> None:
    ss = st.session_state
    if "_prepared" not in ss:
        ss._prepared = {}
        return
    if did is None:
        ss._prepared = {}
    else:
        ss._prepared = {k: v for k, v in ss._prepared.items() if k[0] != did}


def load_demo_workspace(pid: str | None = None) -> str:
    """Create a demo project with preloaded realistic meter data for instant onboarding."""
    ss = st.session_state
    if pid is None:
        pid = create_project("Campus Energy Lab · Building A", "University", "Demo project with historical hourly meter readings")
        ss.active_project_id = pid

    rng = np.random.default_rng(42)
    now = pd.Timestamp.now().floor("h")
    idx = pd.date_range(now - pd.Timedelta(days=60), now, freq="h")
    hour, dow = idx.hour.to_numpy(), idx.dayofweek.to_numpy()
    temp = (25 + 5 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.7, len(idx))).round(1)
    humid = (65 - 10 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 2, len(idx))).clip(20, 95).round(1)
    occ = ((hour >= 8) & (hour < 18)).astype(float) * np.where(dow >= 5, 0.35, 1.0)
    load = ((15 + 45 * occ + 1.8 * np.clip(temp - 24, 0, None)) * (1 + rng.normal(0, 0.05, len(idx)))).round(2)
    load[len(load) - 24 * 12:len(load) - 24 * 11] *= 1.75

    demo_df = pd.DataFrame({
        "timestamp": idx,
        "consumption_kwh": load,
        "temperature_c": temp,
        "humidity_pct": humid,
        "notes": "Smart meter automated feed",
    })

    did = add_dataset(
        pid=pid,
        name="Main Meter — Automated Feed",
        df=demo_df,
        time_col="timestamp",
        target_col="consumption_kwh",
        weather_cols=["temperature_c", "humidity_pct"],
        file_name="demo_meter_feed.csv",
    )
    ss.projects[pid]["active_dataset_id"] = did
    touch(pid)
    return pid


def create_empty_dataset(pid: str, name: str = "Manual Readings Log") -> str:
    """Create a new dataset for manual reading logging."""
    now = pd.Timestamp.now().floor("min")
    initial_df = pd.DataFrame([
        {
            "timestamp": now - pd.Timedelta(hours=2),
            "consumption_kwh": 3.5,
            "temperature_c": 26.5,
            "humidity_pct": 65.0,
            "notes": "Baseline reading",
        },
        {
            "timestamp": now - pd.Timedelta(hours=1),
            "consumption_kwh": 4.2,
            "temperature_c": 27.0,
            "humidity_pct": 63.0,
            "notes": "Regular usage",
        },
    ])
    did = add_dataset(
        pid=pid,
        name=name,
        df=initial_df,
        time_col="timestamp",
        target_col="consumption_kwh",
        weather_cols=["temperature_c", "humidity_pct"],
        file_name="manual_readings.csv",
    )
    st.session_state.datasets[did]["source"] = "manual"
    return did


def update_dataset_df(did: str, new_df: pd.DataFrame) -> None:
    """Update dataset dataframe, clear caches, and touch project."""
    ss = st.session_state
    if did in ss.datasets:
        ss.datasets[did]["df"] = new_df
        invalidate_cache(did)
        touch(ss.datasets[did]["project_id"])


def append_reading(did: str, reading: dict) -> None:
    """Append a single reading record to dataset, sort chronologically, and refresh caches."""
    ss = st.session_state
    if did in ss.datasets:
        df = ss.datasets[did]["df"]
        new_row = pd.DataFrame([reading])
        updated_df = pd.concat([df, new_row], ignore_index=True)
        t_col = ss.datasets[did]["time_col"]
        if t_col in updated_df.columns:
            updated_df[t_col] = pd.to_datetime(updated_df[t_col], errors="coerce")
            updated_df = updated_df.sort_values(t_col).reset_index(drop=True)
        update_dataset_df(did, updated_df)


def active_dataset() -> dict | None:
    proj = active_project()
    if not proj:
        return None
    return st.session_state.datasets.get(proj.get("active_dataset_id"))


def prepared(ds: dict) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Return (series at native freq, daily series, freq) for a dataset, memoised per session."""
    key = (ds["id"], ds["time_col"], ds["target_col"], tuple(ds["weather_cols"]))
    cache = st.session_state._prepared
    if key not in cache:
        series, freq = prepare_series(ds["df"], ds["time_col"], ds["target_col"], ds["weather_cols"])
        cache[key] = (series, to_daily(series), freq)
    return cache[key]


def select_id(label: str, items: dict, current: str | None = None, **kwargs) -> str:
    """Selectbox over {id: display name}; returns the chosen id. Duplicate names get a numeric suffix."""
    labels, seen = {}, {}
    for i, name in items.items():
        seen[name] = seen.get(name, 0) + 1
        labels[f"{name} ({seen[name]})" if seen[name] > 1 else name] = i
    keys = list(labels)
    ids = list(labels.values())
    idx = ids.index(current) if current in ids else 0
    return labels[st.selectbox(label, keys, index=idx, **kwargs)]


def dataset_selector(label: str = "Dataset", key: str = "ds_select") -> dict | None:
    """Selectbox for the active project's datasets; updates the project's active dataset."""
    proj = active_project()
    options = project_datasets(proj["id"]) if proj else []
    if not options:
        return None
    chosen = select_id(label, {d["id"]: d["name"] for d in options}, proj.get("active_dataset_id"),
                       key=f"{key}_{proj['id']}")
    proj["active_dataset_id"] = chosen
    return st.session_state.datasets[chosen]


def settings() -> dict:
    return st.session_state.settings
