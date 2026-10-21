"""Anomaly detection: flag unusual consumption periods for investigation."""

import numpy as np
import pandas as pd
import streamlit as st

from components import charts
from components.layout import page_context
from components.metric_cards import badge, banner, empty_state, footer, kpi_card, section_header
from services.anomaly_service import (METHODS, SENSITIVITY, anomaly_table, detect_statistical, investigation_hint)
from services.api_client import get_client
from services.state import dataset_selector, prepared, settings, touch
from utils.formatting import fmt_energy, unit_factor

ss = st.session_state
proj, ds = page_context("Anomaly Detection",
                        "Find periods where consumption differs strongly from what is typical. "
                        "Each flag is a signal to investigate, not proof of a fault.")
cfg = settings()
unit = cfg["unit"]

# ---------------- Controls ----------------
with st.container(border=True):
    c1, c2, c3, c4, c5 = st.columns([1.4, 1.3, 1.5, 0.9, 0.9], vertical_alignment="bottom")
    with c1:
        ds = dataset_selector("Dataset", key="an_ds")
    series, daily, freq = prepared(ds)
    with c2:
        method = st.selectbox("Detection method", list(METHODS),
                              format_func=lambda m: m + ("" if METHODS[m]["local"] else "  ·  backend"),
                              help="\n\n".join(f"**{k}** — {v['help']}" for k, v in METHODS.items()))
    with c3:
        sens = st.select_slider("Sensitivity", list(SENSITIVITY), value="Medium (recommended)",
                                format_func=lambda s: s.split(" (")[0],
                                help="Higher sensitivity flags more periods (lower z-score threshold). "
                                     "Low: |z| > 4 · Medium: |z| > 3 · High: |z| > 2.25")
    with c4:
        res_opts = ["Daily", "Hourly"] if freq == "hourly" else ["Daily"]
        resolution = st.selectbox("Resolution", res_opts, help="Hourly finds short events; daily finds unusual days.")
    with c5:
        run = st.button("Detect anomalies", type="primary", width="stretch", icon=":material/radar:")
    st.caption(METHODS[method]["help"])

threshold = SENSITIVITY[sens]
data = series if resolution == "Hourly" else daily
cfg_key = {"dataset": ds["id"], "method": method, "threshold": threshold, "resolution": resolution}

if run:
    if METHODS[method]["local"]:
        with st.spinner("Scoring every period against its typical value…"):
            result = detect_statistical(data, "hourly" if resolution == "Hourly" else "daily", threshold)
        ss.anomaly_runs[proj["id"]] = {"config": cfg_key, "result": result, "dataset_source": ds["source"],
                                       "dataset_name": ds["name"], "created": pd.Timestamp.now()}
        touch(proj["id"])
        n = int(result["is_anomaly"].sum())
        st.toast(f"{n} unusual period{'s' if n != 1 else ''} flagged.", icon=":material/radar:")
    else:
        with st.spinner(f"Requesting {method} results from the ML backend…"):
            api = get_client().get_anomalies({"dataset_id": ds["id"], "method": method,
                                              "threshold": threshold, "resolution": resolution.lower()})
        ss.backend_status = api.ok
        if not api.ok:
            st.error(f"**{method} did not run.** {api.error}", icon=":material/cloud_off:")
            st.caption("No anomalies were generated. Start the FastAPI backend, or use the Statistical threshold method.")
        else:
            try:
                result = pd.DataFrame(api.data["results"])
                result["timestamp"] = pd.to_datetime(result["timestamp"])
                ss.anomaly_runs[proj["id"]] = {"config": cfg_key, "result": result, "dataset_source": ds["source"],
                                               "dataset_name": ds["name"], "created": pd.Timestamp.now()}
            except (KeyError, TypeError, ValueError) as exc:
                st.error(f"The backend response was not in the expected format: {exc}")

run_state = ss.anomaly_runs.get(proj["id"])
if run_state is None or run_state["config"]["dataset"] not in ss.datasets:
    empty_state("Run anomaly detection", "Pick a method and sensitivity, then select Detect anomalies. "
                "Medium sensitivity with the Statistical threshold is a good starting point.", "alert")
    footer()
    st.stop()

if run_state["config"] != cfg_key:
    banner("Settings changed since the last run. Select <b>Detect anomalies</b> to refresh the results.", kind="info")

result = run_state["result"]
table = anomaly_table(result)
step = "hour" if run_state["config"]["resolution"] == "Hourly" else "day"

# ---------------- KPIs ----------------
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Flagged periods", f"{len(table):,}", f"of {len(result):,} {step}s analysed", icon_name="alert", tone="red")
with k2:
    kpi_card("High severity", f"{int((table['severity'] == 'High').sum()):,}",
             f"{int((table['severity'] == 'Medium').sum())} medium · {int((table['severity'] == 'Low').sum())} low",
             icon_name="zap", tone="amber")
with k3:
    if len(table):
        worst = table.loc[table["deviation_pct"].abs().idxmax()]
        kpi_card("Largest deviation", f"{worst['deviation_pct']:+.0f}%", f"on {pd.Timestamp(worst['timestamp']):%d %b %Y}",
                 icon_name="activity", tone="navy")
    else:
        kpi_card("Largest deviation", "—", "No anomalies", icon_name="activity", tone="navy")
with k4:
    extra = table.loc[table["deviation"] > 0, "deviation"].sum()
    kpi_card("Excess energy in flags", fmt_energy(extra, unit), "above expected, upward anomalies only",
             icon_name="trending-up", tone="green",
             help_text="Sum of (observed − expected) for periods flagged above expected.")

# ---------------- Chart ----------------
with st.container(border=True):
    section_header("Consumption with highlighted anomalies",
                   f"{run_state['dataset_name']} · {run_state['config']['method']} · |z| > {run_state['config']['threshold']}",
                   badge("Synthetic data", "demo") if run_state["dataset_source"] == "demo" else "")
    show_expected = st.toggle("Show expected consumption", value=True, key="an_expected")
    charts.show(charts.anomaly_chart(result, unit, show_expected=show_expected), key="an_chart")

# ---------------- Table ----------------
section_header("Anomaly details", "Sorted by severity, then most recent")
if table.empty:
    st.success("No periods exceed the selected threshold. Try a higher sensitivity if you expected some.",
               icon=":material/check_circle:")
else:
    f1, f2 = st.columns([1.2, 1])
    sev_f = f1.multiselect("Severity", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    dir_f = f2.segmented_control("Direction", ["All", "Above expected", "Below expected"], default="All", key="an_dir")
    view = table[table["severity"].isin(sev_f)]
    if dir_f and dir_f != "All":
        view = view[view["direction"] == dir_f]

    f = unit_factor(unit)
    out = pd.DataFrame({
        "Reviewed": [str(t) in ss.reviewed_anomalies for t in view["timestamp"]],
        "Timestamp": view["timestamp"].to_numpy(),
        "Severity": view["severity"].to_numpy(),
        f"Observed ({unit})": (view["observed"] * f).round(2).to_numpy(),
        f"Expected ({unit})": (view["expected"] * f).round(2).to_numpy(),
        "Deviation %": view["deviation_pct"].round(1).to_numpy(),
        "Score (z)": view["score"].round(2).to_numpy(),
        "Direction": view["direction"].to_numpy(),
        "What to check": [investigation_hint(r) for _, r in view.iterrows()],
    })
    edited = st.data_editor(
        out, hide_index=True, width="stretch", height=min(420, 38 * (len(out) + 1) + 4),
        disabled=[c for c in out.columns if c != "Reviewed"], key=f"an_editor_{proj['id']}_{'-'.join(sev_f)}_{dir_f}_{len(view)}",
        column_config={
            "Reviewed": st.column_config.CheckboxColumn("Reviewed", help="Mark once investigated (session only)."),
            "Timestamp": st.column_config.DatetimeColumn(format="ddd D MMM YYYY, HH:mm" if step == "hour" else "ddd D MMM YYYY"),
            "Deviation %": st.column_config.NumberColumn(format="%+.1f%%"),
            "Score (z)": st.column_config.NumberColumn(help="Robust z-score: how many typical deviations away from expected."),
            "What to check": st.column_config.TextColumn(width="large"),
        },
    )
    for ts, flag in zip(view["timestamp"], edited["Reviewed"]):
        (ss.reviewed_anomalies.add if flag else ss.reviewed_anomalies.discard)(str(ts))

    export = view.drop(columns=["is_anomaly"]).copy()
    export["data_source"] = "synthetic_demo" if run_state["dataset_source"] == "demo" else "uploaded"
    export["method"] = run_state["config"]["method"]
    export["reviewed"] = [str(t) in ss.reviewed_anomalies for t in view["timestamp"]]
    st.download_button("Export anomalies (CSV)", export.to_csv(index=False).encode("utf-8"), "energy_anomalies.csv",
                       "text/csv", type="primary", icon=":material/download:")

banner("Anomalies show where consumption differed from the usual pattern. Confirm each one with site staff, "
       "maintenance logs or meter checks before concluding there is a fault or waste.", kind="warn", title="Interpretation.")
footer()
