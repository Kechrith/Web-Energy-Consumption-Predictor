# EnergyIntel — Energy Intelligence Platform

A professional Streamlit frontend for analysing electricity consumption, forecasting demand,
detecting unusual usage and evaluating forecasting models. It's built for universities, offices,
factories, hotels and households, and is ready to connect to a FastAPI ML backend.

## Features

| Page | What it does |
|---|---|
| **Energy Predictor** | Appliance energy (Wh) from the trained model in `../artifacts/`, served by `../backend` (`GET /model/info`, `POST /predict`); flags inputs outside the training range |
| **Dashboard** | KPIs (total, daily average, peak, estimated cost, change vs previous period), historical chart, 7-day forecast, actual vs predicted backtest, peak-demand heatmap, recent anomaly alerts, insights, date-range filter, workspace selector |
| **Projects** | Create / rename / archive / delete projects (University, Commercial building, Factory, Hotel, Household); status and last activity |
| **Datasets** | Drag-and-drop CSV/Excel upload, column mapping (timestamp, target, weather), validation (timestamps, gaps, duplicates, types, negatives), numeric and categorical summaries, missing-value chart, preview download |
| **Forecasting** | Dataset/column/model selection, 7–90 day horizon, daily or hourly frequency, empirical prediction intervals, backtest, peak date, CSV export |
| **Anomaly Detection** | Method and sensitivity selection, highlighted chart, observed vs expected, deviation %, severity, review tracking, CSV export |
| **Model Lab** | Chronological train/validation/test split, hyperparameters, progress, ranking, MAE/RMSE/MAPE/R², duration, feature importance, per-experiment inspection |
| **Reports** | Period and section selection, live preview, CSV summary and professionally formatted PDF (ReportLab) |
| **Settings** | Workspace, kWh/MWh, tariff, defaults, backend URL and connection test, data and notification preferences, app info |

### Honesty rules built into the app
- **Synthetic demo data** is generated per site type and labelled everywhere (badges, banners, reports, CSV exports).
- **Local models are real computations.** Seasonal Naive, Seasonal Average and Linear Regression (ridge) actually train on the selected data, and their metrics come from a held-out chronological split. On demo data they are labelled "computed on synthetic data".
- **Backend models are never simulated.** ARIMA, Prophet, Random Forest, XGBoost, Isolation Forest and Autoencoder call the FastAPI service. If it is unreachable, the UI shows an error and reports the model as *not run*.
- Anomalies are presented as signals to investigate, not proof of faults.
- Settings and projects live in `st.session_state` and are marked *not persisted*.

## Project structure

```
energy_intelligence_streamlit/
├── app.py                      # Entry point: page config, theme, navigation
├── pages/                      # One file per page (registered with st.navigation)
│   ├── dashboard.py  projects.py  datasets.py  forecasting.py
│   └── anomaly_detection.py  model_lab.py  reports.py  settings.py
├── components/
│   ├── styles.py               # Design tokens + global CSS
│   ├── icons.py                # Lucide-style inline SVG icons
│   ├── metric_cards.py         # KPI cards, headers, badges, banners, empty states
│   ├── charts.py               # Plotly chart builders
│   ├── layout.py               # Page header + empty-state guards
│   └── sidebar.py              # Workspace switcher + status indicators
├── services/
│   ├── data_service.py         # Demo data, file parsing, series preparation, KPIs
│   ├── forecast_service.py     # Local models, metrics, backtests, chronological split
│   ├── anomaly_service.py      # Robust seasonal z-score detection
│   ├── report_service.py       # Report CSV + PDF rendering
│   ├── api_client.py           # FastAPI client (graceful failure, no fake data)
│   └── state.py                # Session state: projects, datasets, settings
├── utils/
│   ├── validation.py           # Column suggestions, dataset validation, profiles
│   └── formatting.py           # Units, currency, dates
├── assets/                     # logo.svg, icon.svg
├── tests/test_smoke.py         # Renders every page + service tests
├── .streamlit/config.toml      # Theme (navy sidebar, Inter font)
├── .vscode/launch.json         # Run/debug configuration
├── requirements.txt  requirements-dev.txt  .gitignore
```

## Run on Windows

```powershell
cd energy_intelligence_streamlit
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. Python 3.10+ is required.

If PowerShell blocks `activate`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use
`.venv\Scripts\python -m streamlit run app.py` without activating.

### VS Code
1. Open the `energy_intelligence_streamlit` folder.
2. `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv`.
3. Press `F5` and pick **EnergyIntel: Streamlit** (from `.vscode/launch.json`). Breakpoints work and the app reloads on save.

### Tests
```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

## Data format

Upload one row per reading. Column names are detected automatically and can be changed after upload.

| timestamp | consumption_kwh | temperature_c *(optional)* | humidity_pct *(optional)* |
|---|---|---|---|
| 2025-01-01 00:00 | 142.6 | 27.4 | 78 |

Hourly or daily data work best. Sub-hourly readings are summed to hourly. Day-first dates such as `31/01/2025`
are detected. At least 14 days of history are required. A template CSV can be downloaded on the Datasets page.

## Where to connect the real ML backend

The backend in `../backend` currently implements `/health`, `/model/info` and `/predict`. Start it from the
project root with `uvicorn backend.main:app --reload`. The other endpoints below are not built yet.

| What | Where | Endpoint |
|---|---|---|
| Base URL / timeout | Settings page → `services/state.py` `DEFAULT_SETTINGS` | — |
| Energy prediction (trained model) | `pages/predictor.py` → `model_info`, `predict` | `GET /model/info`, `POST /predict` |
| UCI dataset from `../data/raw/` | `pages/datasets.py` → `services/data_service.py` `load_uci_dataset` | — |
| HTTP client | `services/api_client.py` `EnergyIntelAPI` | all |
| Dataset upload | `pages/datasets.py` "Also upload to ML backend" → `upload_dataset` | `POST /datasets` |
| Forecasts (ARIMA, Prophet, RF, XGBoost) | `pages/forecasting.py` backend branch → `create_forecast` | `POST /forecasts` |
| Training jobs | `pages/model_lab.py` → `create_training_job`, `get_training_job` | `POST /training-jobs`, `GET /training-jobs/{id}` |
| Isolation Forest / Autoencoder | `pages/anomaly_detection.py` → `get_anomalies` | `GET /anomalies` |
| Server-side reports | `services/api_client.py` `get_report` | `GET /reports/{id}` |
| Persist projects/settings | replace helpers in `services/state.py` | e.g. `/projects`, `/settings` |

Expected response shapes used by the UI:

```jsonc
// POST /forecasts
{"forecast": [{"timestamp": "...", "forecast": 123.4, "lower": 110.0, "upper": 136.8}],
 "backtest": [{"timestamp": "...", "actual": 120.1, "predicted": 118.7}],
 "metrics": {"MAE": 5.2, "RMSE": 7.1, "MAPE": 4.3, "R2": 0.91}, "duration_s": 3.2}
// POST /training-jobs  → {"job_id": "abc123"}
// GET  /anomalies      → {"results": [{"timestamp": "...", "observed": .., "expected": .., "deviation": ..,
//                          "deviation_pct": .., "score": .., "is_anomaly": true, "severity": "High",
//                          "direction": "Above expected"}]}
// GET  /health         → any 2xx response
```

To add a new **local** model, register it in `LOCAL_MODELS` / `DEFAULT_PARAMS` and add a branch in
`fit_predict()` in `services/forecast_service.py`. Every page and Model Lab picks it up automatically.
