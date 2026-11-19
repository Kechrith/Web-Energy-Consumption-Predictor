"""Energy Predictor: appliance energy use (Wh) from the trained model served by backend/main.py."""

from datetime import datetime

import pandas as pd
import streamlit as st

from components.metric_cards import badge, banner, footer, kpi_card, page_header, section_header
from services.api_client import get_client
from services.state import active_project, append_reading, create_empty_dataset, project_datasets, settings
from utils.formatting import fmt_money

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
        st.error(f"Cannot connect to the ML model backend at `{cfg['api_url']}`.", icon=":material/cloud_off:")
        st.markdown(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:16px; margin: 12px 0;">
                <h4 style="margin:0 0 8px 0; color:#1E293B;">How to start the backend</h4>
                <p style="margin:0 0 10px 0; color:#64748B; font-size:0.9rem;">
                    The Energy Predictor uses the trained model in <code>artifacts/energy_model.joblib</code>, served by FastAPI.
                    Run this command in a terminal from your project root:
                </p>
                <code style="display:block; background:#0F172A; color:#38BDF8; padding:10px 14px; border-radius:6px; font-size:0.9rem;">
                    uvicorn backend.main:app --reload --port 8000
                </code>
                <p style="margin:10px 0 0 0; color:#64748B; font-size:0.85rem;">
                    Once running, click <b>Retry connection</b> below to load the model.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c_r1, c_r2 = st.columns([1, 2])
        with c_r1:
            if st.button("Retry connection", type="primary", icon=":material/refresh:", width="stretch"):
                st.rerun()
        with c_r2:
            st.page_link("pages/settings.py", label="Configure backend URL in Settings", icon=":material/settings:")
        footer()
        st.stop()
    ss.model_info = cached = (cfg["api_url"], res.data)
info = cached[1]
defaults, ranges = info["feature_defaults"], info["feature_ranges"]

# ----------------- Input Mode Selector -----------------
top_m1, top_m2 = st.columns([2, 1], vertical_alignment="center")
with top_m1:
    input_mode = st.radio(
        "Input Mode",
        ["⚡ Quick Estimate (Simple)", "🏠 Room-by-Room (Detailed)"],
        horizontal=True,
        label_visibility="collapsed",
        key="pred_input_mode",
    )
with top_m2:
    if st.button("Use Current Date & Time", icon=":material/schedule:", width="stretch"):
        now_dt = datetime.now()
        ss["pred_form_day"] = now_dt.date()
        ss["pred_form_time"] = now_dt.time()
        st.rerun()

now_dt = datetime.now()
default_day = ss.get("pred_form_day", datetime(2016, 5, 10).date())
default_time = ss.get("pred_form_time", datetime(2016, 5, 10, 18, 0).time())

# Presets Bar
st.caption("Quick Scenarios: click to pre-fill realistic conditions")
sc1, sc2, sc3, sc4 = st.columns(4)
if sc1.button("☀️ Summer Afternoon", help="Warm outdoor (31°C), AC active (22.5°C)", width="stretch"):
    p_vals = {k: 22.5 for k in defaults if k.startswith("T") and k != "T_out"}
    p_vals.update({k: 52.0 for k in defaults if k.startswith("RH_") and k != "RH_out"})
    p_vals.update({"T_out": 31.5, "Press_mm_hg": 756.0, "RH_out": 72.0, "Windspeed": 3.8, "Visibility": 40.0, "Tdewpoint": 21.0, "lights": 10.0})
    ss["pred_presets"] = p_vals
    ss["pred_form_day"] = datetime(2016, 5, 20).date()
    ss["pred_form_time"] = datetime(2016, 5, 20, 14, 0).time()
    st.rerun()

if sc2.button("❄️ Winter Evening", help="Cold outdoor (3°C), indoor heating (21°C), high lights", width="stretch"):
    p_vals = {k: 20.8 for k in defaults if k.startswith("T") and k != "T_out"}
    p_vals.update({k: 40.0 for k in defaults if k.startswith("RH_") and k != "RH_out"})
    p_vals.update({"T_out": 3.2, "Press_mm_hg": 763.0, "RH_out": 85.0, "Windspeed": 5.5, "Visibility": 22.0, "Tdewpoint": -1.5, "lights": 120.0})
    ss["pred_presets"] = p_vals
    ss["pred_form_day"] = datetime(2016, 1, 15).date()
    ss["pred_form_time"] = datetime(2016, 1, 15, 19, 30).time()
    st.rerun()

if sc3.button("🌿 Eco Mode", help="Mild weather (20°C), zero lights, low appliance baseline", width="stretch"):
    p_vals = {k: 21.0 for k in defaults if k.startswith("T") and k != "T_out"}
    p_vals.update({k: 45.0 for k in defaults if k.startswith("RH_") and k != "RH_out"})
    p_vals.update({"T_out": 19.5, "Press_mm_hg": 758.0, "RH_out": 60.0, "Windspeed": 2.2, "Visibility": 45.0, "Tdewpoint": 10.0, "lights": 0.0})
    ss["pred_presets"] = p_vals
    ss["pred_form_day"] = datetime(2016, 4, 10).date()
    ss["pred_form_time"] = datetime(2016, 4, 10, 11, 0).time()
    st.rerun()

if sc4.button("🔄 Reset to Medians", help="Restore all inputs to training median values", width="stretch"):
    ss.pop("pred_presets", None)
    ss.pop("pred_form_day", None)
    ss.pop("pred_form_time", None)
    st.rerun()

current_presets = ss.get("pred_presets", {})


def field(col, name: str, label: str, step: float = 0.1):
    lo, hi = ranges[name]
    default_v = current_presets.get(name, defaults[name])
    return col.number_input(label, value=round(float(default_v), 2), step=step, format="%.2f", key=f"f_{name}_{round(float(default_v), 1)}",
                            help=f"Training range {lo:.1f} – {hi:.1f}. Default is training median.")


# ----------------- PREDICTION FORM -----------------
with st.form("predict_form", border=False):
    values = {}

    if "Simple" in input_mode:
        # Simple Mode: 4 easy intuitive controls
        with st.container(border=True):
            section_header("Time & Lighting")
            c1, c2, c3 = st.columns(3)
            day = c1.date_input("Date", value=default_day)
            time = c2.time_input("Time", value=default_time, step=600)
            lighting_choice = c3.selectbox(
                "Lighting activity",
                ["Off / Low (0 Wh)", "Normal evening (30 Wh)", "Bright / High (90 Wh)"],
                index=1,
            )
            lights_map = {"Off / Low (0 Wh)": 0.0, "Normal evening (30 Wh)": 30.0, "Bright / High (90 Wh)": 90.0}
            values["lights"] = lights_map[lighting_choice]

        with st.container(border=True):
            section_header("Indoor Comfort (Average)")
            ci1, ci2 = st.columns(2)
            avg_temp = ci1.slider("Average Indoor Temperature (°C)", 16.0, 30.0, float(current_presets.get("T1", 21.5)), 0.5)
            avg_humid = ci2.slider("Average Indoor Relative Humidity (%)", 20.0, 85.0, float(current_presets.get("RH_1", 48.0)), 1.0)
            # Auto-populate all 9 rooms evenly
            for i in range(1, 10):
                values[f"T{i}"] = avg_temp
                values[f"RH_{i}"] = avg_humid

        with st.container(border=True):
            section_header("Outdoor Weather")
            co1, co2 = st.columns(2)
            out_temp = co1.slider("Outdoor Temperature (°C)", -10.0, 42.0, float(current_presets.get("T_out", 18.0)), 0.5)
            weather_desc = co2.selectbox("Weather condition", ["Clear / Sunny", "Mild / Overcast", "Humid / Rainy", "Windy"], index=1)

            # Auto-calculate outdoor features realistically
            weather_profiles = {
                "Clear / Sunny": {"RH_out": 50.0, "Press_mm_hg": 760.0, "Windspeed": 2.5, "Visibility": 45.0, "Tdewpoint": out_temp - 6.0},
                "Mild / Overcast": {"RH_out": 68.0, "Press_mm_hg": 756.0, "Windspeed": 3.5, "Visibility": 35.0, "Tdewpoint": out_temp - 4.0},
                "Humid / Rainy": {"RH_out": 88.0, "Press_mm_hg": 750.0, "Windspeed": 4.5, "Visibility": 20.0, "Tdewpoint": out_temp - 1.5},
                "Windy": {"RH_out": 60.0, "Press_mm_hg": 752.0, "Windspeed": 8.0, "Visibility": 40.0, "Tdewpoint": out_temp - 5.0},
            }
            wp = weather_profiles[weather_desc]
            values["T_out"] = out_temp
            values["RH_out"] = wp["RH_out"]
            values["Press_mm_hg"] = wp["Press_mm_hg"]
            values["Windspeed"] = wp["Windspeed"]
            values["Visibility"] = wp["Visibility"]
            values["Tdewpoint"] = wp["Tdewpoint"]

    else:
        # Detailed Mode: Clean collapsible sections for rooms
        with st.container(border=True):
            section_header("Time & Lighting")
            a, b, c = st.columns(3)
            day = a.date_input("Date", value=default_day)
            time = b.time_input("Time", value=default_time, step=600)
            values["lights"] = field(c, "lights", "Lights (Wh)", step=10.0)

        with st.expander("🛋️ Common Living Areas (Kitchen, Living, Laundry)", expanded=True):
            common_rooms = [(1, "Kitchen"), (2, "Living room"), (3, "Laundry room")]
            for i, room in common_rooms:
                a, b, c = st.columns([1.3, 1, 1], vertical_alignment="bottom")
                a.markdown(f"**{room}**")
                values[f"T{i}"] = field(b, f"T{i}", f"T{i} (°C)")
                values[f"RH_{i}"] = field(c, f"RH_{i}", f"RH_{i} (%)")

        with st.expander("🛏️ Bedrooms & Office", expanded=True):
            bed_rooms = [(4, "Office room"), (8, "Teenager room"), (9, "Parents room"), (7, "Ironing room")]
            for i, room in bed_rooms:
                a, b, c = st.columns([1.3, 1, 1], vertical_alignment="bottom")
                a.markdown(f"**{room}**")
                values[f"T{i}"] = field(b, f"T{i}", f"T{i} (°C)")
                values[f"RH_{i}"] = field(c, f"RH_{i}", f"RH_{i} (%)")

        with st.expander("🚪 Bathroom & North Side", expanded=False):
            other_rooms = [(5, "Bathroom"), (6, "Outside (north side)")]
            for i, room in other_rooms:
                a, b, c = st.columns([1.3, 1, 1], vertical_alignment="bottom")
                a.markdown(f"**{room}**")
                values[f"T{i}"] = field(b, f"T{i}", f"T{i} (°C)")
                values[f"RH_{i}"] = field(c, f"RH_{i}", f"RH_{i} (%)")

        with st.expander("⛅ Outdoor Weather Details", expanded=False):
            cols = st.columns(3)
            for j, (name, label) in enumerate(OUTDOOR.items()):
                values[name] = field(cols[j % 3], name, label)

    st.write("")
    submitted = st.form_submit_button("Predict Energy Consumption", type="primary", icon=":material/bolt:")

# ----------------- INFERENCE & RESULTS -----------------
if submitted:
    payload = {"timestamp": datetime.combine(day, time).isoformat(), **values}
    with st.spinner("Requesting prediction from ML model…"):
        res = client.predict(payload)
    ss.backend_status = res.ok
    if res.ok:
        ss.last_prediction = res.data
    else:
        ss.pop("last_prediction", None)
        st.error(f"Prediction failed. {res.error}", icon=":material/error:")

pred = ss.get("last_prediction")
if pred:
    pred_wh = pred["predicted_energy_wh"]
    pred_cost = (pred_wh / 1000.0) * float(cfg["tariff"])
    test = info["metrics"].get("test", {})
    mae = test.get("MAE", 30.0)

    st.write("")
    section_header("Prediction Results", "Appliance electricity use predicted by the trained model")

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Predicted Appliance Energy", f"{pred_wh:,.1f} Wh", "per 10-minute reading", icon_name="zap", tone="blue")
    with k2:
        kpi_card("Estimated Reading Cost", fmt_money(pred_cost, cfg["currency"]), f"at {cfg['tariff']:.3f} {cfg['currency']}/kWh", icon_name="dollar", tone="green")
    with k3:
        kpi_card("Model Precision (MAE)", f"± {mae:,.1f} Wh", pred["model_name"], icon_name="check", tone="navy")

    for w in pred["warnings"]:
        banner(w, kind="warn", title="Outside training data.")

    # One-click save to project readings
    proj = active_project()
    if proj:
        save_col1, save_col2 = st.columns([2, 1], vertical_alignment="center")
        with save_col1:
            st.caption(f"💾 Save this reading ({pred_wh:.1f} Wh) to active project “{proj['name']}”.")
        with save_col2:
            if st.button("Save reading to project", icon=":material/save:", width="stretch"):
                dsets = project_datasets(proj["id"])
                did = proj.get("active_dataset_id") or (dsets[0]["id"] if dsets else None)
                if not did:
                    did = create_empty_dataset(proj["id"], f"{proj['name']} — Meter Log")

                pred_kwh = round(pred_wh / 1000.0, 4)
                new_rec = {
                    "timestamp": datetime.combine(day, time),
                    "consumption_kwh": pred_kwh,
                    "temperature_c": float(values.get("T_out", 20.0)),
                    "humidity_pct": float(values.get("RH_out", 50.0)),
                    "notes": f"Predicted ({pred['model_name']})",
                }
                append_reading(did, new_rec)
                st.toast(f"Saved {pred_kwh} kWh to {proj['name']}!", icon=":material/check_circle:")

with st.expander("Model details & performance metrics", icon=":material/info:"):
    st.write(f"**Model:** {info['model_name']} · **Features:** {len(info['features'])}")
    st.dataframe(pd.DataFrame(info["metrics"]).T.rename_axis("Split").reset_index(), hide_index=True, use_container_width=True)
    st.caption("Metrics come from artifacts/energy_model.joblib (training/train.py).")

footer()
