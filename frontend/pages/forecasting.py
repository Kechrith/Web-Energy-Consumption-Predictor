"""Forecasting workspace: configure a model, generate a forecast, inspect and export it."""

import numpy as np
import pandas as pd
import streamlit as st

from components import charts
from components.layout import page_context
from components.metric_cards import badge, banner, empty_state, footer, kpi_card, section_header
from services.api_client import get_client
from services.data_service import prepare_series
from services.forecast_service import (ALL_MODELS, BACKEND_MODELS, DEFAULT_PARAMS, LOCAL_MODELS, run_forecast)
from services.state import dataset_selector, settings, touch
from utils.formatting import fmt_date, fmt_energy, unit_factor

ss = st.session_state
proj, ds = page_context("Forecasting", "Predict future consumption, check how the model performed on recent data, and export the results.")
cfg = settings()
unit = cfg["unit"]

controls, results = st.columns([1, 2.6], gap="large")

# ---------------- Controls ----------------
with controls, st.container(border=True):
    st.markdown("**Forecast setup**")
    ds = dataset_selector("Dataset", key="fc_ds")
    df = ds["df"]
    cols = list(df.columns)
    numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    time_col = st.selectbox("Timestamp column", cols, index=cols.index(ds["time_col"]) if ds["time_col"] in cols else 0)
    target_col = st.selectbox("Target column", numeric or cols,
                              index=(numeric or cols).index(ds["target_col"]) if ds["target_col"] in (numeric or cols) else 0,
                              help="The quantity to forecast, usually energy consumption in kWh.")

    series, native_freq = prepare_series(df, time_col, target_col, [])
    model = st.selectbox(
        "Model", ALL_MODELS,
        index=ALL_MODELS.index(cfg["default_model"]) if cfg["default_model"] in ALL_MODELS else 0,
        format_func=lambda m: f"{m}  ·  local" if m in LOCAL_MODELS else f"{m}  ·  backend",
        help="Local models run here on your data. Backend models are sent to the FastAPI ML service.",
    )
    st.caption({**LOCAL_MODELS, **BACKEND_MODELS}[model])

    horizon = st.segmented_control("Horizon (days)", [7, 14, 30, 60, 90],
                                   default=cfg["default_horizon"] if cfg["default_horizon"] in [7, 14, 30, 60, 90] else 7,
                                   key="fc_horizon") or 7
    hourly_ok = native_freq == "hourly"
    freq_label = st.radio("Frequency", ["Daily", "Hourly"], horizontal=True, index=0,
                          disabled=not hourly_ok,
                          help="Hourly forecasting needs hourly (or finer) data." if hourly_ok
                          else "Disabled: this dataset is not hourly.")
    freq = "hourly" if (freq_label == "Hourly" and hourly_ok) else "daily"
    if freq == "hourly" and horizon > 30:
        st.caption("Long hourly horizons produce many points; consider daily frequency beyond 30 days.")

    show_interval = st.toggle("Prediction interval", value=True,
                              help="Range expected to contain the actual value. Here it is estimated from errors "
                                   "on recent held-out data (empirical interval).")
    level = st.select_slider("Interval level", [0.8, 0.9, 0.95], value=0.9, format_func=lambda v: f"{v:.0%}",
                             disabled=not show_interval)

    params = dict(DEFAULT_PARAMS.get(model, {}))
    with st.expander("Hyperparameters"):
        if model == "Seasonal Naive":
            st.caption("No hyperparameters.")
        elif model == "Seasonal Average":
            params["weeks"] = st.slider("Weeks to average", 1, 8, params["weeks"])
        elif model == "Linear Regression":
            params["alpha"] = st.number_input("Ridge alpha (regularisation)", 0.0, 100.0, float(params["alpha"]), 0.5)
            st.caption("Weather features are not used for forecasting because future weather is unknown.")
        else:
            for k, v in params.items():
                if isinstance(v, str):
                    params[k] = st.text_input(k, v)
                elif isinstance(v, int):
                    params[k] = st.number_input(k, value=v, step=1)
                else:
                    params[k] = st.number_input(k, value=float(v), format="%.3f")

    go = st.button("Generate forecast", type="primary", width="stretch", icon=":material/play_arrow:")

if freq == "daily":
    series = series.resample("D").sum(min_count=1).interpolate() if native_freq == "hourly" else series
config = {"dataset": ds["id"], "time": time_col, "target": target_col, "model": model, "horizon": horizon,
          "freq": freq, "interval": level if show_interval else None, "params": params}

if go:
    if series.empty or len(series) < 15:
        st.error("Not enough valid rows to forecast. Check the timestamp and target columns.")
    elif model in LOCAL_MODELS:
        with st.spinner(f"Fitting {model} and generating a {horizon}-day forecast…"):
            try:
                res = run_forecast(series, freq, model, horizon, params, interval=config["interval"])
                res.update(config=config, dataset_name=ds["name"], dataset_source=ds["source"], history=series["y"])
                ss.forecasts[proj["id"]] = res
                touch(proj["id"])
                st.toast("Forecast generated.", icon=":material/check_circle:")
            except ValueError as exc:
                st.error(str(exc))
    else:
        with st.spinner(f"Requesting {model} forecast from the ML backend…"):
            api = get_client().create_forecast({
                "dataset_id": ds["id"], "target": target_col, "time_col": time_col, "model": model,
                "horizon_days": horizon, "frequency": freq, "interval": config["interval"], "params": params,
            })
        ss.backend_status = api.ok
        if not api.ok:
            with controls:
                st.error(f"**{model} forecast not generated.** {api.error}", icon=":material/cloud_off:")
                st.caption("No predictions were created. Start the FastAPI backend, or pick a local model.")
        else:
            try:
                fc = pd.DataFrame(api.data["forecast"])
                fc["timestamp"] = pd.to_datetime(fc["timestamp"])
                res = {"model": model, "freq": freq, "horizon_days": horizon, "interval": config["interval"],
                       "forecast": fc, "backtest": pd.DataFrame(api.data.get("backtest", [])),
                       "metrics": api.data.get("metrics", {}), "importance": None, "duration_s": api.data.get("duration_s"),
                       "created": pd.Timestamp.now(), "source": "backend", "config": config,
                       "dataset_name": ds["name"], "dataset_source": ds["source"], "history": series["y"]}
                if not res["backtest"].empty:
                    res["backtest"]["timestamp"] = pd.to_datetime(res["backtest"]["timestamp"])
                ss.forecasts[proj["id"]] = res
                st.toast("Backend forecast received.", icon=":material/cloud_done:")
            except (KeyError, TypeError, ValueError) as exc:
                st.error(f"The backend response was not in the expected format: {exc}")

# ---------------- Results ----------------
with results:
    res = ss.forecasts.get(proj["id"])
    if res is None or res["config"]["dataset"] not in ss.datasets:
        empty_state("No forecast yet", "Choose a model and horizon on the left, then select Generate forecast. "
                    "Seasonal Naive is a quick, reliable baseline to start with.", "trending-up")
    else:
        if res["config"] != config:
            banner("The settings on the left have changed since this forecast was generated. "
                   "Select <b>Generate forecast</b> to update it.", kind="info")
        fc = res["forecast"]
        step_label = "hour" if res["freq"] == "hourly" else "day"
        is_demo = res["dataset_source"] == "demo"
        source_tag = badge("Local model", "info") if res["source"] == "local" else badge("Backend model", "real")
        data_tag = badge("Synthetic data", "demo") if is_demo else badge("Uploaded data", "real")
        st.markdown(f"**{res['model']}** · {res['horizon_days']}-day {res['freq']} forecast for *{res['dataset_name']}* "
                    f"&nbsp;{source_tag} {data_tag}", unsafe_allow_html=True)

        peak = fc.loc[fc["forecast"].idxmax()]
        m = res.get("metrics") or {}
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Forecast total", fmt_energy(fc["forecast"].sum(), unit), f"next {res['horizon_days']} days", icon_name="zap")
        with k2:
            per_day = fc["forecast"].sum() / res["horizon_days"]
            kpi_card("Average per day", fmt_energy(per_day, unit, 1 if unit == "kWh" else 2), "predicted", icon_name="activity", tone="navy")
        with k3:
            fmt = "%a %d %b, %H:00" if res["freq"] == "hourly" else "%a %d %b %Y"
            kpi_card("Expected peak", pd.Timestamp(peak["timestamp"]).strftime(fmt),
                     f"{fmt_energy(peak['forecast'], unit, 1)} per {step_label}", icon_name="gauge", tone="amber")
        with k4:
            mape = m.get("MAPE", np.nan)
            kpi_card("Backtest error (MAPE)", f"{mape:.1f}%" if mape is not None and not np.isnan(mape) else "n/a",
                     f"MAE {fmt_energy(m.get('MAE', np.nan), unit, 1)} per {step_label}", icon_name="check", tone="green",
                     help_text="Mean absolute percentage error on the most recent held-out period. Lower is better.")

        with st.container(border=True):
            section_header("Historical and forecast consumption",
                           "Dashed line: forecast · shaded band: prediction interval" if res["interval"] else "Dashed line: forecast")
            hist = res["history"]
            lookback = 21 * 24 if res["freq"] == "hourly" else 90
            charts.show(charts.forecast_chart(hist.tail(lookback), fc, unit, height=380,
                                              show_interval=bool(res["interval"]),
                                              interval_label=f"{res['interval']:.0%} interval" if res["interval"] else ""),
                        key="fc_main")

        t1, t2, t3 = st.tabs(["Actual vs predicted", "Forecast table", "Model details"])
        with t1:
            bt = res["backtest"]
            if bt is None or bt.empty:
                st.info("The backend did not return backtest results.")
            else:
                st.caption(f"The model was trained without the last {len(bt):,} {step_label}s, then asked to predict them. "
                           "This shows how well it handles data it has not seen.")
                charts.show(charts.actual_vs_predicted(bt, unit), key="fc_avp")
                mc = st.columns(4)
                mc[0].metric("MAE", fmt_energy(m.get("MAE", np.nan), unit, 1), help="Mean absolute error: average size of the miss.")
                mc[1].metric("RMSE", fmt_energy(m.get("RMSE", np.nan), unit, 1), help="Root mean squared error: penalises large misses more.")
                mc[2].metric("MAPE", f"{m['MAPE']:.1f}%" if not np.isnan(m.get("MAPE", np.nan)) else "n/a",
                             help="Mean absolute percentage error. Not shown when actual values are near zero.")
                mc[3].metric("R²", f"{m['R2']:.3f}" if not np.isnan(m.get("R2", np.nan)) else "n/a",
                             help="Share of variance explained (1 = perfect; below 0 = worse than predicting the mean).")
        with t2:
            f = unit_factor(unit)
            table = fc.copy()
            out = pd.DataFrame({"Timestamp": table["timestamp"], f"Forecast ({unit})": (table["forecast"] * f).round(3)})
            if "lower" in table:
                out[f"Lower ({unit})"] = (table["lower"] * f).round(3)
                out[f"Upper ({unit})"] = (table["upper"] * f).round(3)
            st.dataframe(out, hide_index=True, width="stretch", height=320,
                         column_config={"Timestamp": st.column_config.DatetimeColumn(
                             format="ddd D MMM YYYY, HH:mm" if res["freq"] == "hourly" else "ddd D MMM YYYY")})
            export = out.copy()
            export.insert(1, "model", res["model"])
            export["data_source"] = "synthetic_demo" if is_demo else "uploaded"
            st.download_button("Export forecast (CSV)", export.to_csv(index=False).encode("utf-8"),
                               f"forecast_{res['model'].replace(' ', '_').lower()}_{res['horizon_days']}d.csv", "text/csv",
                               type="primary", icon=":material/download:")
        with t3:
            st.markdown(f"- **Model:** {res['model']} ({'computed locally in this app' if res['source'] == 'local' else 'FastAPI backend'})\n"
                        f"- **Dataset:** {res['dataset_name']}\n"
                        f"- **Target / time:** `{res['config']['target']}` / `{res['config']['time']}`\n"
                        f"- **Generated:** {fmt_date(res['created'], with_time=True)}"
                        + (f" in {res['duration_s']:.2f} s" if res.get("duration_s") else ""))
            st.json(res["config"]["params"] or {"hyperparameters": "none"}, expanded=False)
            if res.get("importance") is not None:
                st.markdown("**Feature importance** (standardised coefficients)")
                charts.show(charts.importance_chart(res["importance"]), key="fc_imp")

st.caption("Local models are simple statistical baselines computed on the selected data. ARIMA, Prophet, Random Forest "
           "and XGBoost require the FastAPI backend — connect them in `services/api_client.py` → `create_forecast`.")
footer()
