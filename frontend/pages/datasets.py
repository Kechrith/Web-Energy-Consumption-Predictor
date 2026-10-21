"""Dataset management: upload, column mapping, validation and data-quality inspection."""

from pathlib import Path

import pandas as pd
import streamlit as st

from components import charts
from components.metric_cards import badge, banner, check_list, empty_state, footer, page_header, section_header
from services.api_client import get_client
from services.data_service import UCI_DATA_PATH, load_uci_dataset, read_uploaded_file
from services.state import (active_project, add_dataset, delete_dataset, project_datasets, select_id, settings,
                            touch)
from utils.formatting import fmt_date
from utils.validation import (categorical_summary, column_profile, numeric_summary, suggest_columns,
                              validate_dataset)

ss = st.session_state
cfg = settings()
proj = active_project()
page_header("Datasets", "Upload historical meter data, map its columns, and check quality before analysis.",
            eyebrow=cfg["workspace_name"] + (f" · {proj['name']}" if proj else ""))
if proj is None:
    empty_state("No project selected", "Datasets belong to a project. Create one first.", "folder")
    st.page_link("pages/projects.py", label="Go to Projects", icon=":material/arrow_forward:")
    st.stop()

ss.setdefault("uploader_key", 0)


def mapping_controls(df: pd.DataFrame, key: str, current: dict | None = None) -> dict:
    """Column selectors for timestamp, target and weather features."""
    sug = current or suggest_columns(df)
    cols = list(df.columns)
    numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    a, b, c = st.columns([1, 1, 1.4])
    tc = a.selectbox("Timestamp column *", cols, index=cols.index(sug["time_col"]) if sug["time_col"] in cols else 0,
                     key=f"{key}_time", help="Date or date-time of each reading.")
    target_opts = numeric or cols
    tg_default = sug["target_col"] if sug["target_col"] in target_opts else target_opts[0]
    tg = b.selectbox("Consumption column *", target_opts, index=target_opts.index(tg_default), key=f"{key}_target",
                     help="Energy consumed per period, e.g. kWh. This is what the models predict.")
    weather_opts = [x for x in numeric if x not in (tc, tg)]
    wc = c.multiselect("Weather / extra features (optional)", weather_opts,
                       default=[w for w in sug["weather_cols"] if w in weather_opts], key=f"{key}_weather",
                       help="Numeric drivers such as temperature or humidity. Used by Linear Regression in Model Lab.")
    return {"time_col": tc, "target_col": tg, "weather_cols": wc}


def quality_report(df: pd.DataFrame, mapping: dict, key: str) -> bool:
    """Render validation + inspection tabs. Returns True if the dataset is usable."""
    rep = validate_dataset(df, mapping["time_col"], mapping["target_col"], mapping["weather_cols"])
    left, right = st.columns([1.15, 1])
    with left:
        section_header("Validation", "Checks run against the selected column mapping")
        check_list(rep.checks)
    with right:
        section_header("Summary")
        m1, m2 = st.columns(2)
        m1.metric("Rows", f"{len(df):,}")
        m2.metric("Columns", len(df.columns))
        m3, m4 = st.columns(2)
        missing = int(df.isna().sum().sum())
        m3.metric("Missing cells", f"{missing:,}", help=f"{missing / max(df.size, 1):.2%} of all cells")
        m4.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
        m5, m6 = st.columns(2)
        m5.metric("Frequency", rep.frequency.capitalize())
        m6.metric("Span", f"{(rep.end - rep.start).days + 1:,} days" if rep.start is not None else "—",
                  help=f"{fmt_date(rep.start)} → {fmt_date(rep.end)}" if rep.start is not None else None)

    profile = column_profile(df)
    t1, t2, t3, t4, t5 = st.tabs(["Preview", "Column types", "Numeric summary", "Categorical summary", "Missing values"])
    with t1:
        n = st.select_slider("Rows to preview", [10, 25, 50, 100, 250], value=25, key=f"{key}_n")
        st.dataframe(df.head(n), hide_index=True, width="stretch")
        st.download_button("Download preview (CSV)", df.head(1000).to_csv(index=False).encode("utf-8"),
                           file_name="dataset_preview.csv", mime="text/csv", icon=":material/download:", key=f"{key}_dl")
    with t2:
        st.dataframe(profile, hide_index=True, width="stretch",
                     column_config={"Missing %": st.column_config.ProgressColumn("Missing %", min_value=0, max_value=100, format="%.1f%%")})
    with t3:
        ns = numeric_summary(df)
        if ns.empty:
            st.info("No numeric columns found.")
        else:
            st.dataframe(ns, hide_index=True, width="stretch")
            target = mapping["target_col"]
            if target in df.columns and pd.api.types.is_numeric_dtype(df[target]):
                charts.show(charts.distribution_chart(df[target], target), key=f"{key}_dist")
    with t4:
        cs = categorical_summary(df)
        if cs.empty:
            st.info("No categorical or text columns found.")
        else:
            st.dataframe(cs, hide_index=True, width="stretch")
    with t5:
        charts.show(charts.missing_values_chart(profile, height=max(200, 40 * len(profile))), key=f"{key}_miss")
    return rep.ok, rep


@st.dialog("Delete dataset")
def confirm_delete(did: str) -> None:
    d = ss.datasets[did]
    st.write(f"Delete **{d['name']}** from this project?")
    st.caption("Forecasts already generated from it stay in the session until you regenerate them.")
    a, b = st.columns(2)
    if a.button("Cancel", width="stretch"):
        st.rerun()
    if b.button("Delete", type="primary", width="stretch"):
        delete_dataset(did)
        st.toast("Dataset deleted.", icon=":material/delete:")
        st.rerun()


tab_upload, tab_library = st.tabs(["Upload dataset", f"Project datasets ({len(project_datasets(proj['id']))})"])

# ---------------- Upload ----------------
with tab_upload:
    upload = st.file_uploader(
        "Drag and drop a CSV or Excel file", type=["csv", "xlsx", "xls"], key=f"uploader_{ss.uploader_key}",
        help="Needs at least a timestamp column and a numeric consumption column. Hourly or daily readings work best.",
    )
    if upload is None:
        st.markdown(
            f"""<div class="ei-card" style="margin-top:.5rem"><b>Recommended format</b>
            <div class="ei-item-body" style="margin-top:.35rem">One row per reading. Column names are detected automatically
            and you can change the mapping after upload. {badge('timestamp', 'info')} {badge('consumption_kwh', 'info')}
            {badge('temperature_c (optional)', 'muted')} {badge('humidity_pct (optional)', 'muted')}</div></div>""",
            unsafe_allow_html=True,
        )
        sample = pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=48, freq="h"),
                               "consumption_kwh": 100.0, "temperature_c": 28.0, "humidity_pct": 75.0})
        st.download_button("Download a template CSV", sample.to_csv(index=False).encode("utf-8"), "energyintel_template.csv",
                           "text/csv", icon=":material/download:")

        st.divider()
        section_header("Project dataset", "The UCI Appliances Energy data the backend model is trained on (data/raw/)")
        if UCI_DATA_PATH.exists():
            if st.button("Load energydata_complete.csv", icon=":material/folder_open:"):
                with st.spinner("Reading data/raw/energydata_complete.csv…"):
                    uci = load_uci_dataset()
                add_dataset(proj["id"], "UCI Appliances Energy (data/raw)", uci, "date", "appliances_kwh",
                            ["T_out", "RH_out"], UCI_DATA_PATH.name)
                st.toast("UCI dataset added and selected for analysis.", icon=":material/check_circle:")
                st.rerun()
        else:
            st.info(f"Place `energydata_complete.csv` in `{UCI_DATA_PATH.parent}` to load it here. "
                    "See the project README for the download link.", icon=":material/info:")
    else:
        cache_key = f"parsed_{upload.file_id}"
        if cache_key not in ss:
            with st.spinner(f"Reading {upload.name}…"):
                ss[cache_key] = read_uploaded_file(upload)
        df, err = ss[cache_key]
        if err:
            st.error(f"**Could not load {upload.name}.** {err}", icon=":material/error:")
            st.caption("Tips: save Excel files as .xlsx, make sure the first row contains column names, "
                       "and use a consistent date format such as 2025-01-31 14:00.")
        else:
            st.success(f"Loaded **{upload.name}** — {len(df):,} rows × {len(df.columns)} columns.", icon=":material/check_circle:")
            section_header("Column mapping", "Tell EnergyIntel which columns hold time, consumption and optional drivers")
            mapping = mapping_controls(df, key="up")
            ok, rep = quality_report(df, mapping, key="up")

            st.divider()
            section_header("Save to project", f"The dataset will be added to “{proj['name']}” and selected for analysis")
            with st.form("save_ds", border=False):
                a, b = st.columns([2, 1], vertical_alignment="bottom")
                name = a.text_input("Dataset name *", value=Path(upload.name).stem.replace("_", " ").title(), max_chars=80)
                send = b.checkbox("Also upload to ML backend", value=False,
                                  help="Sends the file to POST /datasets on the FastAPI service configured in Settings.")
                submitted = st.form_submit_button("Save dataset", type="primary", disabled=not ok, icon=":material/save:")
            if not ok:
                st.error("Fix the validation errors above before saving: " + " ".join(rep.errors))
            if submitted:
                if not name.strip():
                    st.error("Enter a dataset name.")
                else:
                    stored = df if cfg["keep_raw_upload"] else df[[mapping["time_col"], mapping["target_col"], *mapping["weather_cols"]]]
                    add_dataset(proj["id"], name, stored, mapping["time_col"], mapping["target_col"],
                                mapping["weather_cols"], upload.name)
                    if send:
                        with st.spinner("Uploading to backend…"):
                            res = get_client().upload_dataset(df, name, **mapping)
                        ss.backend_status = res.ok
                        if res.ok:
                            st.toast("Dataset uploaded to the ML backend.", icon=":material/cloud_done:")
                        else:
                            st.toast(f"Saved locally only — backend upload failed: {res.error}", icon=":material/cloud_off:")
                    ss.pop(cache_key, None)
                    ss.uploader_key += 1
                    st.toast(f"“{name.strip()}” saved and selected for analysis.", icon=":material/check_circle:")
                    st.rerun()

# ---------------- Library ----------------
with tab_library:
    dsets = project_datasets(proj["id"])
    if not dsets:
        empty_state("No datasets in this project", "Upload a file in the Upload tab to get started.", "database")
    else:
        table = pd.DataFrame([{
            "Name": d["name"], "Source": "Synthetic demo" if d["source"] == "demo" else "Upload",
            "File": d["file_name"], "Rows": len(d["df"]), "Target": d["target_col"],
            "Added": d["created"].strftime("%d %b %Y %H:%M"),
            "In use": d["id"] == proj.get("active_dataset_id"),
        } for d in dsets])
        st.dataframe(table, hide_index=True, width="stretch",
                     column_config={"In use": st.column_config.CheckboxColumn("In use", help="Dataset used by analytics pages")})

        cur = proj.get("active_dataset_id")
        did = select_id("Inspect dataset", {d["id"]: d["name"] for d in dsets}, cur)
        d = ss.datasets[did]
        a, b, c = st.columns(3)
        if a.button("Use for analysis", disabled=did == cur, width="stretch", icon=":material/check:"):
            proj["active_dataset_id"] = did
            touch(proj["id"])
            st.rerun()
        c.download_button("Download full CSV", d["df"].to_csv(index=False).encode("utf-8"),
                          f"{d['name'].replace(' ', '_')}.csv", "text/csv", width="stretch", icon=":material/download:")
        if b.button("Delete dataset", width="stretch", icon=":material/delete:"):
            if cfg["confirm_delete"]:
                confirm_delete(did)
            else:
                delete_dataset(did)
                st.rerun()

        if d["source"] == "demo":
            banner("This dataset is generated by the app. It includes injected unusual events so anomaly detection "
                   "can be demonstrated. It does not represent a real site.", kind="demo", title="Synthetic data.")
        with st.expander("Edit column mapping", icon=":material/edit:"):
            new_map = mapping_controls(d["df"], key=f"lib_{did}", current={
                "time_col": d["time_col"], "target_col": d["target_col"], "weather_cols": d["weather_cols"]})
            if st.button("Apply mapping", key=f"apply_{did}"):
                rep = validate_dataset(d["df"], **new_map)
                if rep.ok:
                    d.update(new_map)
                    touch(proj["id"])
                    st.toast("Column mapping updated.", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error(" ".join(rep.errors))
        quality_report(d["df"], {"time_col": d["time_col"], "target_col": d["target_col"],
                                 "weather_cols": d["weather_cols"]}, key=f"lib_{did}")

footer()
