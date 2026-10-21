"""Session-state management for projects, datasets, settings, and results.

Everything here lives in `st.session_state` only — it is lost when the browser
session ends. Replace these helpers with `api_client` calls to persist on the backend.
"""

from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from services.data_service import generate_demo_data, prepare_series, to_daily

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
    "show_demo_labels": True,
    "keep_raw_upload": True,
    "notify_anomalies": True,
    "notify_training": True,
    "notify_email": "",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _demo_dataset(site_type: str, project_id: str) -> dict:
    df = generate_demo_data(site_type)
    return {
        "id": _new_id("ds"),
        "name": f"Demo · {site_type} meter (synthetic)",
        "project_id": project_id,
        "source": "demo",
        "df": df,
        "time_col": "timestamp",
        "target_col": "consumption_kwh",
        "weather_cols": ["temperature_c", "humidity_pct"],
        "created": pd.Timestamp.now(),
        "file_name": "generated in app",
    }


def init_state() -> None:
    ss = st.session_state
    if "settings" not in ss:
        ss.settings = dict(DEFAULT_SETTINGS)
    if "projects" not in ss:
        ss.projects, ss.datasets = {}, {}
        now = pd.Timestamp.now()
        seeds = [
            ("University Campus", "University", "Main campus building meters.", now - pd.Timedelta(hours=2)),
            ("Office Building", "Commercial building", "Weekday/weekend office load patterns.", now - pd.Timedelta(days=1, hours=3)),
            ("Factory Demo", "Factory", "Shift-based industrial load.", now - pd.Timedelta(days=4)),
        ]
        for name, site, desc, last in seeds:
            pid = create_project(name, site, desc, with_demo=True)
            ss.projects[pid]["last_activity"] = last
        ss.active_project_id = next(iter(ss.projects))
    ss.setdefault("forecasts", {})      # project_id -> last forecast result dict
    ss.setdefault("experiments", {})    # project_id -> list of experiment dicts
    ss.setdefault("anomaly_runs", {})   # project_id -> last anomaly result dict
    ss.setdefault("reviewed_anomalies", set())
    ss.setdefault("_prepared", {})


# ---------------- Projects ----------------
def create_project(name: str, site_type: str, description: str = "", with_demo: bool = True) -> str:
    pid = _new_id("prj")
    now = pd.Timestamp.now()
    st.session_state.projects[pid] = {
        "id": pid, "name": name.strip(), "site_type": site_type, "description": description.strip(),
        "status": "Active", "created": now, "last_activity": now, "active_dataset_id": None,
    }
    if with_demo:
        ds = _demo_dataset(site_type, pid)
        st.session_state.datasets[ds["id"]] = ds
        st.session_state.projects[pid]["active_dataset_id"] = ds["id"]
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
    ss._prepared = {k: v for k, v in ss._prepared.items() if k[0] != did}


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
