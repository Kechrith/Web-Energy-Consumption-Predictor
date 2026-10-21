"""Projects: create, open, organise and manage energy analysis projects."""

import streamlit as st

from components.metric_cards import badge, footer, page_header, section_header
from services.data_service import SITE_TYPES
from services.state import create_project, delete_project, name_taken, project_datasets, settings, touch
from utils.formatting import fmt_date, time_ago

ss = st.session_state
cfg = settings()
page_header("Projects", "Organise datasets, forecasts and experiments by site or business unit.",
            eyebrow=cfg["workspace_name"])

STATUS_BADGE = {"Active": "real", "Draft": "info", "Archived": "muted"}
SITE_ICON = {"University": ":material/school:", "Commercial building": ":material/apartment:",
             "Factory": ":material/factory:", "Hotel": ":material/hotel:", "Household": ":material/home:"}


@st.dialog("Delete project")
def confirm_delete(pid: str) -> None:
    p = ss.projects[pid]
    n = len(project_datasets(pid))
    st.write(f"Delete **{p['name']}** and its {n} dataset(s), forecasts and experiments?")
    st.caption("This only affects the current browser session, but it cannot be undone.")
    a, b = st.columns(2)
    if a.button("Cancel", width="stretch"):
        st.rerun()
    if b.button("Delete project", type="primary", width="stretch"):
        delete_project(pid)
        st.toast(f"Deleted project “{p['name']}”.", icon=":material/delete:")
        st.rerun()


# ---------- Summary ----------
projects = list(ss.projects.values())
m1, m2, m3, m4 = st.columns(4)
m1.metric("Projects", len(projects))
m2.metric("Active", sum(p["status"] == "Active" for p in projects))
m3.metric("Datasets", len(ss.datasets))
m4.metric("Experiments", sum(len(v) for v in ss.experiments.values()))

# ---------- Create ----------
with st.expander("Create a new project", icon=":material/add:", expanded=not projects):
    with st.form("new_project", clear_on_submit=True, border=False):
        a, b = st.columns(2)
        name = a.text_input("Project name *", placeholder="e.g. Phnom Penh Campus — Building A", max_chars=60)
        site = b.selectbox("Site type *", SITE_TYPES)
        desc = st.text_area("Description", placeholder="What will this project analyse?", height=80, max_chars=240)
        with_demo = st.checkbox("Start with a synthetic demo dataset for this site type", value=True,
                                help="Useful for exploring the app. You can upload real data later on the Datasets page.")
        if st.form_submit_button("Create project", type="primary"):
            if not name.strip():
                st.error("Enter a project name.")
            elif name_taken(name):
                st.error("A project with this name already exists.")
            else:
                pid = create_project(name, site, desc, with_demo=with_demo)
                ss.active_project_id = pid
                st.toast(f"Project “{name.strip()}” created and set as active.", icon=":material/check_circle:")
                st.rerun()

# ---------- List ----------
c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
with c1:
    section_header("Your projects", "The active project is used on every analytics page.")
with c2:
    status_filter = st.segmented_control("Status", ["All", "Active", "Draft", "Archived"], default="All",
                                         label_visibility="collapsed", key="proj_filter")
shown = [p for p in projects if status_filter in (None, "All") or p["status"] == status_filter]
shown.sort(key=lambda p: p["last_activity"], reverse=True)

if not shown:
    st.info("No projects match this filter.")

cols = st.columns(3)
for i, p in enumerate(shown):
    with cols[i % 3], st.container(border=True):
        is_active = p["id"] == ss.get("active_project_id")
        dsets = project_datasets(p["id"])
        n_exp = len(ss.experiments.get(p["id"], []))
        head = f"**{p['name']}**"
        st.markdown(head)
        st.markdown(
            f"{badge(p['site_type'], 'info')} {badge(p['status'], STATUS_BADGE[p['status']])}"
            f"{' ' + badge('Active project', 'real') if is_active else ''}",
            unsafe_allow_html=True,
        )
        st.caption(p["description"] or "No description.")
        x, y, z = st.columns(3)
        x.markdown(f"<div class='ei-kpi-label'>Datasets</div><b>{len(dsets)}</b>", unsafe_allow_html=True)
        y.markdown(f"<div class='ei-kpi-label'>Experiments</div><b>{n_exp}</b>", unsafe_allow_html=True)
        z.markdown(f"<div class='ei-kpi-label'>Forecast</div><b>{'Yes' if p['id'] in ss.forecasts else '—'}</b>",
                   unsafe_allow_html=True)
        st.caption(f"Last activity {time_ago(p['last_activity'])} · created {fmt_date(p['created'])}")

        b1, b2 = st.columns(2)
        if b1.button("Open", key=f"open_{p['id']}", type="primary" if not is_active else "secondary",
                     width="stretch", icon=SITE_ICON.get(p["site_type"]),
                     help="Make this the active project and open its dashboard"):
            ss.active_project_id = p["id"]
            touch(p["id"])
            st.switch_page("pages/dashboard.py")
        with b2.popover("Manage", width="stretch", icon=":material/tune:"):
            new_name = st.text_input("Name", p["name"], key=f"rn_{p['id']}")
            new_status = st.selectbox("Status", ["Active", "Draft", "Archived"],
                                      index=["Active", "Draft", "Archived"].index(p["status"]), key=f"st_{p['id']}")
            if st.button("Save changes", key=f"save_{p['id']}", width="stretch"):
                if not new_name.strip():
                    st.error("Name cannot be empty.")
                elif name_taken(new_name, exclude=p["id"]):
                    st.error("Another project already uses this name.")
                else:
                    p["name"], p["status"] = new_name.strip(), new_status
                    touch(p["id"])
                    st.rerun()
            st.divider()
            if st.button("Delete project", key=f"del_{p['id']}", icon=":material/delete:", width="stretch"):
                if cfg["confirm_delete"]:
                    confirm_delete(p["id"])
                else:
                    delete_project(p["id"])
                    st.rerun()
        if dsets:
            with st.expander(f"Datasets ({len(dsets)})"):
                for d in dsets:
                    st.markdown(f"- {d['name']}  \n  <span style='color:#64748B;font-size:.8rem'>"
                                f"{len(d['df']):,} rows · added {fmt_date(d['created'])}</span>", unsafe_allow_html=True)

st.caption("Projects are stored in this browser session only. Connect `GET/POST /projects` on the backend to persist them.")
footer()
