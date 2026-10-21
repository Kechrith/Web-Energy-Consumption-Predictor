"""EnergyIntel — Energy Intelligence Platform (Streamlit frontend).

Run with:  streamlit run app.py
"""

import streamlit as st

from components.sidebar import render_sidebar
from components.styles import inject_styles
from services.state import init_state

st.set_page_config(
    page_title="EnergyIntel · Energy Intelligence Platform",
    page_icon="assets/icon.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
init_state()
st.logo("assets/logo.svg", icon_image="assets/icon.svg", size="large")

pages = {
    "Analytics": [
        st.Page("pages/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
        st.Page("pages/predictor.py", title="Energy Predictor", icon=":material/bolt:"),
        st.Page("pages/forecasting.py", title="Forecasting", icon=":material/trending_up:"),
        st.Page("pages/anomaly_detection.py", title="Anomaly Detection", icon=":material/warning:"),
    ],
    "Workspace": [
        st.Page("pages/projects.py", title="Projects", icon=":material/folder:"),
        st.Page("pages/datasets.py", title="Datasets", icon=":material/database:"),
        st.Page("pages/model_lab.py", title="Model Lab", icon=":material/science:"),
        st.Page("pages/reports.py", title="Reports", icon=":material/description:"),
    ],
    "System": [
        st.Page("pages/settings.py", title="Settings", icon=":material/settings:"),
    ],
}

nav = st.navigation(pages, position="sidebar")
render_sidebar()
nav.run()
