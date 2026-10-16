"""Settings: workspace, units, defaults, backend connection, preferences, app information."""

import platform

import pandas as pd
import plotly
import streamlit as st

from components.metric_cards import badge, banner, footer, page_header, section_header
from services.api_client import EnergyIntelAPI
from services.forecast_service import ALL_MODELS
from services.state import DEFAULT_SETTINGS, settings

ss = st.session_state
cfg = settings()
page_header("Settings", "Configure the workspace, defaults and backend connection.", eyebrow=cfg["workspace_name"],
            badges=[badge("Session only — not persisted", "demo")])
banner("Settings are kept for this browser session only. Persist them through a backend endpoint "
       "(e.g. <code>PUT /settings</code>) for production use.", kind="info", title="Not yet persisted.")

with st.form("settings_form", border=False):
    with st.container(border=True):
        section_header("Workspace")
        a, b = st.columns(2)
        workspace = a.text_input("Workspace name", cfg["workspace_name"], max_chars=60)
        unit = b.segmented_control("Preferred energy unit", ["kWh", "MWh"], default=cfg["unit"])
        c, d = st.columns(2)
        tariff = c.number_input("Electricity tariff (per kWh)", 0.0, 10.0, float(cfg["tariff"]), 0.005, format="%.3f",
                                help="Flat rate used for cost estimates on the Dashboard and in Reports.")
        currency = d.selectbox("Currency", ["USD", "KHR", "EUR"], index=["USD", "KHR", "EUR"].index(cfg["currency"]))

    with st.container(border=True):
        section_header("Forecasting defaults")
        a, b = st.columns(2)
        horizon = a.selectbox("Default horizon", [7, 14, 30, 60, 90], index=[7, 14, 30, 60, 90].index(cfg["default_horizon"]),
                              format_func=lambda d: f"{d} days")
        model = b.selectbox("Default model", ALL_MODELS, index=ALL_MODELS.index(cfg["default_model"]),
                            help="Backend models need a reachable FastAPI service. The dashboard always uses a local model.")

    with st.container(border=True):
        section_header("ML backend (FastAPI)")
        a, b = st.columns([3, 1])
        api_url = a.text_input("Backend base URL", cfg["api_url"], placeholder="http://localhost:8000")
        timeout = b.number_input("Timeout (s)", 1, 60, int(cfg["api_timeout"]))

    with st.container(border=True):
        section_header("Data management")
        confirm = st.toggle("Ask for confirmation before deleting projects or datasets", cfg["confirm_delete"])
        demo_labels = st.toggle("Show demo-data banners", cfg["show_demo_labels"],
                                help="Badges on charts and reports always remain, even when banners are hidden.")
        keep_raw = st.toggle("Keep all uploaded columns (not only mapped ones)", cfg["keep_raw_upload"])

    with st.container(border=True):
        section_header("Notifications", "Delivery requires the backend; in this frontend they are preferences only")
        a, b = st.columns(2)
        n_anom = a.toggle("Notify on high-severity anomalies", cfg["notify_anomalies"])
        n_train = b.toggle("Notify when training jobs finish", cfg["notify_training"])
        email = st.text_input("Notification email", cfg["notify_email"], placeholder="name@example.com")

    saved = st.form_submit_button("Save settings", type="primary", icon=":material/save:")

if saved:
    errors = []
    if not workspace.strip():
        errors.append("Workspace name cannot be empty.")
    if api_url and not api_url.startswith(("http://", "https://")):
        errors.append("Backend URL must start with http:// or https://.")
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        errors.append("Notification email does not look valid.")
    if errors:
        for e in errors:
            st.error(e)
    else:
        if api_url.strip() != cfg["api_url"]:
            ss.backend_status = None
        cfg.update(workspace_name=workspace.strip(), unit=unit or "kWh", tariff=tariff, currency=currency,
                   default_horizon=horizon, default_model=model, api_url=api_url.strip(), api_timeout=timeout,
                   confirm_delete=confirm, show_demo_labels=demo_labels, keep_raw_upload=keep_raw,
                   notify_anomalies=n_anom, notify_training=n_train, notify_email=email.strip())
        st.toast("Settings saved for this session.", icon=":material/check_circle:")
        st.rerun()

# ---------------- Connection test ----------------
a, b, _ = st.columns([1, 1, 2])
if a.button("Test backend connection", icon=":material/lan:", width="stretch"):
    with st.spinner(f"Contacting {cfg['api_url']}…"):
        res = EnergyIntelAPI(cfg["api_url"], timeout=float(cfg["api_timeout"])).health()
    ss.backend_status = res.ok
    if res.ok:
        st.success(f"Connected to {cfg['api_url']}. Response: {res.data}", icon=":material/cloud_done:")
    else:
        st.error(res.error, icon=":material/cloud_off:")


@st.dialog("Reset settings")
def confirm_reset():
    st.write("Restore all settings to their defaults?")
    x, y = st.columns(2)
    if x.button("Cancel", width="stretch"):
        st.rerun()
    if y.button("Reset", type="primary", width="stretch"):
        ss.settings = dict(DEFAULT_SETTINGS)
        st.rerun()


if b.button("Reset to defaults", icon=":material/restart_alt:", width="stretch"):
    confirm_reset()

# ---------------- App info ----------------
with st.expander("Application information", icon=":material/info:"):
    st.dataframe(pd.DataFrame([
        ("Application", "EnergyIntel frontend 1.0"),
        ("Streamlit", st.__version__), ("Pandas", pd.__version__), ("Plotly", plotly.__version__),
        ("Python", platform.python_version()),
        ("Local models", "Seasonal Naive, Seasonal Average, Linear Regression (ridge)"),
        ("Backend models", "ARIMA, Prophet, Random Forest, XGBoost (via FastAPI)"),
        ("Anomaly methods", "Statistical threshold (local); Isolation Forest, Autoencoder (backend)"),
        ("Data storage", "Browser session (st.session_state) — cleared when the session ends"),
    ], columns=["Item", "Value"]), hide_index=True, width="stretch")

footer()
