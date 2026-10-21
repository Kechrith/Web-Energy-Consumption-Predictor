"""Page scaffolding shared by every page: header, data-source badge, empty-state guards."""

import streamlit as st

from components.metric_cards import badge, demo_banner, empty_state, page_header
from services.state import active_dataset, active_project, settings


def source_badge(ds: dict | None) -> str:
    if ds is None:
        return badge("No data", "muted")
    return badge("Demo data", "demo") if ds["source"] == "demo" else badge("Uploaded data", "real")


def page_context(title: str, subtitle: str, need_dataset: bool = True, demo_note: str | None = None):
    """Render the page header and stop the page with a helpful empty state if prerequisites are missing."""
    proj, ds = active_project(), active_dataset()
    eyebrow = settings()["workspace_name"] + (f" · {proj['name']}" if proj else "")
    page_header(title, subtitle, eyebrow=eyebrow, badges=[source_badge(ds)] if need_dataset else None)

    if proj is None:
        empty_state("No project selected", "Create a project to organise datasets, forecasts and experiments.", "folder")
        st.page_link("pages/projects.py", label="Go to Projects", icon=":material/arrow_forward:")
        st.stop()
    if need_dataset and ds is None:
        empty_state("This project has no dataset yet",
                    "Upload a CSV or Excel file with a timestamp column and an energy consumption column.", "database")
        st.page_link("pages/datasets.py", label="Upload a dataset", icon=":material/upload:")
        st.stop()
    if need_dataset and ds["source"] == "demo":
        demo_banner(demo_note or "This project is using a synthetic demonstration dataset.")
    return proj, ds
