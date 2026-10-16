"""Sidebar extras rendered under Streamlit's native navigation."""

from html import escape

import streamlit as st

from services.state import active_dataset, active_project, select_id


def _status_row(color: str, text: str) -> str:
    return f'<div class="ei-side-status"><span class="ei-dot" style="background:{color};"></span>{escape(text)}</div>'


def render_sidebar() -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown('<div class="ei-side-label">Workspace</div>', unsafe_allow_html=True)
        projects = ss.projects
        if projects:
            chosen = select_id(
                "Active project", {i: p["name"] for i, p in projects.items()}, ss.get("active_project_id"),
                label_visibility="collapsed", help="All pages analyse the active project's selected dataset.",
            )
            ss.active_project_id = chosen
        else:
            st.caption("No projects yet — create one on the Projects page.")

        proj, ds = active_project(), active_dataset()
        rows = []
        if proj:
            rows.append(_status_row("#60A5FA", f"{proj['site_type']} · {proj['status']}"))
        if ds is None:
            rows.append(_status_row("#94A3B8", "No dataset selected"))
        elif ds["source"] == "demo":
            rows.append(_status_row("#F59E0B", "Synthetic demo data"))
        else:
            rows.append(_status_row("#22C55E", f"Uploaded: {ds['file_name']}"))
        backend = ss.get("backend_status")
        if backend is True:
            rows.append(_status_row("#22C55E", "ML backend connected"))
        elif backend is False:
            rows.append(_status_row("#EF4444", "ML backend unreachable"))
        else:
            rows.append(_status_row("#94A3B8", "ML backend not checked"))
        st.markdown("".join(rows), unsafe_allow_html=True)
