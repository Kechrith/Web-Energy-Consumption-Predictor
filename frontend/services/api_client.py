"""HTTP client for the (future) EnergyIntel FastAPI ML backend.

Every method returns an `ApiResult`. Network problems never raise into the UI and never
produce fake data — `ok` is False and `error` explains what happened.

Implemented by backend/main.py:
  GET  /health
  GET  /model/info               {model_name, features, metrics, feature_defaults, feature_ranges}
  POST /predict                  backend.schemas.PredictionRequest -> PredictionResponse

Expected endpoints (not yet implemented in the backend):
  POST /datasets                multipart upload + column mapping
  GET  /datasets
  POST /training-jobs            {dataset_id, target, time_col, models, params, split}
  GET  /training-jobs/{job_id}   {status, progress, results}
  POST /forecasts                {dataset_id, model, horizon, frequency, interval}
  GET  /anomalies                ?dataset_id=&method=&sensitivity=
  GET  /reports/{report_id}
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests


@dataclass
class ApiResult:
    ok: bool
    data: Any = None
    error: str | None = None
    status_code: int | None = None


class EnergyIntelAPI:
    def __init__(self, base_url: str, timeout: float = 5.0, token: str | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    # ---------- core ----------
    def _request(self, method: str, path: str, **kwargs) -> ApiResult:
        if not self.base_url.startswith(("http://", "https://")):
            return ApiResult(False, error="Backend URL is not configured. Set it on the Settings page.")
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.exceptions.ConnectionError:
            return ApiResult(False, error=f"Cannot reach the backend at {self.base_url}. Is the FastAPI server running?")
        except requests.exceptions.Timeout:
            return ApiResult(False, error=f"The backend did not respond within {self.timeout:g} s.")
        except requests.exceptions.RequestException as exc:
            return ApiResult(False, error=f"Request failed: {exc}")

        try:
            payload = resp.json() if resp.content else None
        except json.JSONDecodeError:
            payload = resp.text
        if not resp.ok:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            return ApiResult(False, data=payload, error=f"Backend returned HTTP {resp.status_code}: {detail}",
                             status_code=resp.status_code)
        return ApiResult(True, data=payload, status_code=resp.status_code)

    # ---------- endpoints ----------
    def health(self) -> ApiResult:
        return self._request("GET", "/health")

    def model_info(self) -> ApiResult:
        return self._request("GET", "/model/info")

    def predict(self, payload: dict) -> ApiResult:
        return self._request("POST", "/predict", json=payload)

    def upload_dataset(self, df: pd.DataFrame, name: str, time_col: str, target_col: str,
                       weather_cols: list[str]) -> ApiResult:
        buf = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
        meta = {"name": name, "time_col": time_col, "target_col": target_col, "weather_cols": weather_cols}
        return self._request("POST", "/datasets", files={"file": (f"{name}.csv", buf, "text/csv")},
                             data={"metadata": json.dumps(meta)})

    def list_datasets(self) -> ApiResult:
        return self._request("GET", "/datasets")

    def create_training_job(self, payload: dict) -> ApiResult:
        return self._request("POST", "/training-jobs", json=payload)

    def get_training_job(self, job_id: str) -> ApiResult:
        return self._request("GET", f"/training-jobs/{job_id}")

    def create_forecast(self, payload: dict) -> ApiResult:
        return self._request("POST", "/forecasts", json=payload)

    def get_anomalies(self, params: dict) -> ApiResult:
        return self._request("GET", "/anomalies", params=params)

    def get_report(self, report_id: str) -> ApiResult:
        return self._request("GET", f"/reports/{report_id}")


def get_client() -> EnergyIntelAPI:
    """Build a client from the current session settings."""
    import streamlit as st

    s = st.session_state.get("settings", {})
    return EnergyIntelAPI(s.get("api_url", ""), timeout=float(s.get("api_timeout", 5)))
