"""Smoke tests: every page renders without exceptions, and core services compute sane results.

Run:  python -m pytest -q
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["dashboard", "predictor", "projects", "datasets", "forecasting", "anomaly_detection", "model_lab", "reports", "settings"]


def _app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = _app()
    at.switch_page(f"pages/{page}.py").run()
    assert not at.exception, [e.value for e in at.exception]


def _click(at: AppTest, label: str) -> AppTest:
    btn = next(b for b in at.button if b.label == label)
    btn.click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_forecast_generation():
    at = _app()
    at.switch_page("pages/forecasting.py").run()
    _click(at, "Generate forecast")
    proj = at.session_state["active_project_id"]
    res = at.session_state["forecasts"][proj]
    assert len(res["forecast"]) == 7 and res["source"] == "local"


def test_backend_model_fails_gracefully():
    at = _app()
    at.session_state["settings"]["api_url"] = "http://127.0.0.1:9"  # nothing listens here
    at.switch_page("pages/forecasting.py").run()
    at.selectbox[3].select("XGBoost").run()  # dataset, time, target, model
    _click(at, "Generate forecast")
    assert any("not generated" in e.value for e in at.error)
    assert at.session_state["active_project_id"] not in at.session_state["forecasts"]


def test_anomaly_and_model_lab_and_report():
    at = _app()
    at.switch_page("pages/anomaly_detection.py").run()
    _click(at, "Detect anomalies")
    at.switch_page("pages/model_lab.py").run()
    _click(at, "Train models")
    proj = at.session_state["active_project_id"]
    exp = at.session_state["experiments"][proj][-1]
    assert all(r["status"] == "Completed" for r in exp["results"])
    at.switch_page("pages/reports.py").run()
    assert not at.exception


def test_services():
    from services.anomaly_service import detect_statistical
    from services.data_service import generate_demo_data, prepare_series, to_daily
    from services.forecast_service import evaluate_local_model, regression_metrics, run_forecast
    from utils.validation import suggest_columns, validate_dataset

    df = generate_demo_data.__wrapped__("Hotel") if hasattr(generate_demo_data, "__wrapped__") else generate_demo_data("Hotel")
    sug = suggest_columns(df)
    assert sug == {"time_col": "timestamp", "target_col": "consumption_kwh", "weather_cols": ["temperature_c", "humidity_pct"]}
    assert validate_dataset(df, **sug).ok
    series, freq = prepare_series(df, **sug)
    assert freq == "hourly" and series["y"].isna().sum() == 0
    daily = to_daily(series)
    res = run_forecast(daily, "daily", "Linear Regression", 14)
    assert len(res["forecast"]) == 14 and (res["forecast"]["lower"] <= res["forecast"]["upper"]).all()
    ev = evaluate_local_model(series, "hourly", "Linear Regression", {"alpha": 1.0, "use_weather": True}, 70, 15)
    assert ev["test_metrics"]["R2"] > 0.5
    an = detect_statistical(daily, "daily", 3.0)
    assert an["is_anomaly"].sum() >= 1
    m = regression_metrics([0, 1, 2], [0, 1, 2])
    assert np.isnan(m["MAPE"]) and m["MAE"] == 0


def test_validation_errors():
    from utils.validation import validate_dataset

    bad = pd.DataFrame({"when": ["not a date"] * 30, "kwh": ["x"] * 30})
    rep = validate_dataset(bad, "when", "kwh")
    assert not rep.ok and len(rep.errors) >= 2


def test_dayfirst_dates_and_messy_csv():
    from services.data_service import prepare_series, read_uploaded_file
    from utils.validation import suggest_columns, validate_dataset

    class Upload:
        name = "meter.csv"

        def __init__(self, data):
            self._d = data

        def getvalue(self):
            return self._d

    rows = ["Date;Usage (kWh);Temp;Site"]
    for i, d in enumerate(pd.date_range("2025-01-01", periods=60)):
        if i != 10:
            rows.append(f"{d:%d/%m/%Y};{1000 + i * 3 if i != 20 else 'n/a'};{28 + i % 5};A")
    df, err = read_uploaded_file(Upload("\n".join(rows).encode()))
    assert err is None
    sug = suggest_columns(df)
    assert sug["time_col"] == "Date" and sug["target_col"] == "Usage (kWh)"
    rep = validate_dataset(df, **sug)
    assert rep.ok and rep.frequency == "daily"
    series, freq = prepare_series(df, **sug)
    assert freq == "daily" and len(series) == 60 and series.index[0] == pd.Timestamp("2025-01-01")
