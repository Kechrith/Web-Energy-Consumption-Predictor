"""Page scaffolding shared by every page: header, data-source badge, empty-state guards."""

import streamlit as st

from components.metric_cards import badge, empty_state, page_header
from services.state import active_dataset, active_project, settings


def source_badge(ds: dict | None) -> str:
    return badge("No data", "muted") if ds is None else badge("Uploaded data", "real")


def page_context(title: str, subtitle: str, need_dataset: bool = True):
    """Render the page header and stop the page with a helpful empty state if prerequisites are missing."""
    proj, ds = active_project(), active_dataset()
    eyebrow = settings()["workspace_name"] + (f" · {proj['name']}" if proj else "")
    page_header(title, subtitle, eyebrow=eyebrow, badges=[source_badge(ds)] if need_dataset else None)

    if proj is None:
        empty_state("No project selected", "Get started immediately with sample data, or create your own project.", "folder")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚀 Load Sample Project & Data (1-Click)", type="primary", icon=":material/rocket_launch:", width="stretch"):
                from services.state import load_demo_workspace
                load_demo_workspace()
                st.rerun()
        with c2:
            st.page_link("pages/projects.py", label="Create custom project", icon=":material/arrow_forward:")
        st.stop()
    if need_dataset and ds is None:
        empty_state("This project has no dataset yet",
                    "Add readings manually, load sample data, or upload a CSV file.", "database")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("⚡ Initialize Sample Readings", type="primary", icon=":material/add_chart:", width="stretch"):
                from services.state import load_demo_workspace
                load_demo_workspace(proj["id"])
                st.rerun()
        with c2:
            st.page_link("pages/readings.py", label="Add readings manually", icon=":material/edit_calendar:")
        with c3:
            st.page_link("pages/datasets.py", label="Upload CSV / Excel", icon=":material/upload:")
        st.stop()
    return proj, ds
