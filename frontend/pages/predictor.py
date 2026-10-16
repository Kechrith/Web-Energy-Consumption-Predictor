"""Energy Predictor: appliance energy use (Wh) from the trained model served by backend/main.py."""

from datetime import datetime

import pandas as pd
import streamlit as st

from components.metric_cards import badge, banner, footer, kpi_card, page_header, section_header
from services.api_client import get_client
from services.state import settings

ROOMS = ["Kitchen", "Living room", "Laundry room", "Office room", "Bathroom", "Outside (north side)",
         "Ironing room", "Teenager room", "Parents room"]
OUTDOOR = {"T_out": "Outdoor temperature (°C)", "Press_mm_hg": "Pressure (mm Hg)", "RH_out": "Outdoor humidity (%)",
           "Windspeed": "Wind speed (m/s)", "Visibility": "Visibility (km)", "Tdewpoint": "Dew point (°C)"}

ss = st.session_state
cfg = settings()
page_header("Energy Predictor", "Predict household appliance energy use from indoor, outdoor and time conditions.",
            eyebrow=cfg["workspace_name"], badges=[badge("Trained model · FastAPI", "real")])

client = get_client()
cached = ss.get("model_info")
if cached is None or cached[0] != cfg["api_url"]:
    with st.spinner(f"Loading model information from {cfg['api_url']}…"):
        res = client.model_info()
    ss.backend_status = res.ok
    if not res.ok:
        st.error(res.error, icon=":material/cloud_off:")
        st.caption("Start the backend from the project root with `uvicorn backend.main:app --reload`, "
                   "then check the backend URL on the Settings page.")
        st.button("Retry", icon=":material/refresh:")
        footer()
        st.stop()
    ss.model_info = cached = (cfg["api_url"], res.data)
info = cached[1]
defaults, ranges = info["feature_defaults"], info["feature_ranges"]


def field(col, name: str, label: str, step: float = 0.1):
    lo, hi = ranges[name]
    return col.number_input(label, value=round(float(defaults[name]), 2), step=step, format="%.2f", key=f"pred_{name}",
                            help=f"Training range {lo:.1f} – {hi:.1f}. Default is the training median.")


with st.form("predict_form", border=False):
    with st.container(border=True):
        section_header("Time and lights")
        a, b, c = st.columns(3)
        day = a.date_input("Date", datetime(2016, 5, 10))
        time = b.time_input("Time", datetime(2016, 5, 10, 18, 0).time(), step=600)
        values = {"lights": field(c, "lights", "Lights (Wh)", step=10.0)}

    with st.container(border=True):
        section_header("Indoor conditions", "Temperature (°C) and relative humidity (%) per room")
        for i, room in enumerate(ROOMS, start=1):
            a, b, c = st.columns([1.3, 1, 1], vertical_alignment="bottom")
            a.markdown(f"**{room}**")
            values[f"T{i}"] = field(b, f"T{i}", f"T{i} (°C)")
            values[f"RH_{i}"] = field(c, f"RH_{i}", f"RH_{i} (%)")

    with st.container(border=True):
        section_header("Outdoor weather")
        cols = st.columns(3)
        for j, (name, label) in enumerate(OUTDOOR.items()):
            values[name] = field(cols[j % 3], name, label)

    submitted = st.form_submit_button("Predict energy use", type="primary", icon=":material/bolt:")

if submitted:
    payload = {"timestamp": datetime.combine(day, time).isoformat(), **values}
    with st.spinner("Requesting prediction…"):
        res = client.predict(payload)
    ss.backend_status = res.ok
    if res.ok:
        ss.last_prediction = res.data
    else:
        ss.pop("last_prediction", None)
        st.error(f"Prediction failed. {res.error}", icon=":material/error:")

pred = ss.get("last_prediction")
if pred:
    test = info["metrics"].get("test", {})
    a, b = st.columns(2)
    with a:
        kpi_card("Predicted appliance energy", f"{pred['predicted_energy_wh']:,.1f} Wh", foot="per 10-minute reading",
                 icon_name="zap", tone="blue")
    with b:
        kpi_card("Typical error (test MAE)", f"± {test.get('MAE', float('nan')):,.1f} Wh", foot=pred["model_name"],
                 icon_name="info", tone="navy")
    for w in pred["warnings"]:
        banner(w, kind="warn", title="Outside training data.")

with st.expander("Model information", icon=":material/info:"):
    st.write(f"**Model:** {info['model_name']} · **Features:** {len(info['features'])}")
    st.dataframe(pd.DataFrame(info["metrics"]).T.rename_axis("Split").reset_index(), hide_index=True, width="stretch")
    st.caption("Metrics come from artifacts/energy_model.joblib (training/train.py). "
               "Sudden high-usage spikes are hard to predict from environmental readings alone.")

footer()
