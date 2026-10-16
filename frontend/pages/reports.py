"""Reports: assemble a stakeholder report from available, computed results."""

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

from components.layout import page_context
from components.metric_cards import footer, section_header
from services.anomaly_service import anomaly_table, detect_statistical
from services.data_service import period_kpis, previous_period
from services.report_service import build_pdf, report_rows
from services.state import dataset_selector, prepared, settings
from utils.formatting import fmt_date, fmt_energy, fmt_money, fmt_pct

ss = st.session_state
proj, ds = page_context("Reports", "Build a concise energy report for stakeholders. Only results that exist are included.")
cfg = settings()
unit = cfg["unit"]

# ---------------- Options ----------------
with st.container(border=True):
    c1, c2, c3 = st.columns([1.3, 1.4, 1.6], vertical_alignment="bottom")
    with c1:
        ds = dataset_selector("Dataset", key="rep_ds")
    series, daily, freq = prepared(ds)
    lo, hi = daily.index.min().date(), daily.index.max().date()
    with c2:
        period_sel = st.date_input("Report period", value=(max(lo, hi - pd.Timedelta(days=29)), hi),
                                   min_value=lo, max_value=hi, format="DD/MM/YYYY")
    with c3:
        title = st.text_input("Report title", f"Energy Consumption Report — {proj['name']}", max_chars=90)
    include = st.pills("Sections", ["Consumption", "Forecast", "Model evaluation", "Anomalies", "Insights"],
                       selection_mode="multi", default=["Consumption", "Forecast", "Model evaluation", "Anomalies", "Insights"])
    author = st.text_input("Prepared by", placeholder="Name, role (optional)")

if not (isinstance(period_sel, (tuple, list)) and len(period_sel) == 2):
    st.info("Select an end date to complete the report period.")
    st.stop()
start, end = pd.Timestamp(period_sel[0]), pd.Timestamp(period_sel[1])
period = daily.loc[start:end]
if period.empty:
    st.warning("No data in the selected period.")
    st.stop()

# ---------------- Assemble ----------------
k = period_kpis(period, cfg["tariff"])
prev = previous_period(daily, start, end)
kp = period_kpis(prev, cfg["tariff"]) if len(prev) == len(period) else {}
change = (k["total"] - kp["total"]) / kp["total"] * 100 if kp.get("total") else np.nan
is_demo = ds["source"] == "demo"

meta = {"Project": proj["name"], "Site type": proj["site_type"], "Dataset": ds["name"],
        "Period": f"{fmt_date(start)} – {fmt_date(end)}", "Generated": fmt_date(pd.Timestamp.now(), True)}
if author.strip():
    meta["Prepared by"] = author.strip()
sections = []

if "Consumption" in include:
    sections.append({"title": "Energy consumption summary", "rows": [
        ("Total consumption", fmt_energy(k["total"], unit)),
        ("Average daily consumption", fmt_energy(k["avg"], unit, 1 if unit == "kWh" else 2)),
        ("Peak day", f"{fmt_energy(k['peak'], unit)} on {fmt_date(k['peak_date'])}"),
        ("Estimated cost", f"{fmt_money(k['cost'], cfg['currency'])} (flat tariff {cfg['tariff']:.3f} {cfg['currency']}/kWh)"),
        ("Change vs previous period", fmt_pct(change) if not np.isnan(change) else "Not available (insufficient earlier data)"),
    ]})

if "Forecast" in include:
    fc = ss.forecasts.get(proj["id"])
    if fc and fc["config"]["dataset"] == ds["id"]:
        f = fc["forecast"]
        pk = f.loc[f["forecast"].idxmax()]
        m = fc.get("metrics") or {}
        rows = [("Model", f"{fc['model']} ({'local' if fc['source'] == 'local' else 'backend'})"),
                ("Horizon", f"{fc['horizon_days']} days, {fc['freq']}"),
                ("Forecast total", fmt_energy(f["forecast"].sum(), unit)),
                ("Expected peak", f"{pd.Timestamp(pk['timestamp']):%a %d %b %Y}" + (f" {pd.Timestamp(pk['timestamp']):%H:00}" if fc["freq"] == "hourly" else "")),
                ("Generated", fmt_date(fc["created"], True))]
        if m.get("MAPE") is not None and not np.isnan(m.get("MAPE", np.nan)):
            rows.append(("Backtest MAPE", f"{m['MAPE']:.1f}%"))
        sections.append({"title": "Forecast summary", "rows": rows})
    else:
        sections.append({"title": "Forecast summary", "notes": ["No forecast has been generated for this dataset yet. "
                                                                "Generate one on the Forecasting page to include it."]})

if "Model evaluation" in include:
    exps = [e for e in ss.experiments.get(proj["id"], []) if e["dataset_name"] == ds["name"]]
    done = [r for r in (exps[-1]["results"] if exps else []) if r["status"] == "Completed"]
    if done:
        tbl = pd.DataFrame([{"Model": r["model"], "MAE": f"{r['test_metrics']['MAE']:,.2f}",
                             "RMSE": f"{r['test_metrics']['RMSE']:,.2f}",
                             "MAPE %": "n/a" if np.isnan(r["test_metrics"]["MAPE"]) else f"{r['test_metrics']['MAPE']:.2f}",
                             "R²": "n/a" if np.isnan(r["test_metrics"]["R2"]) else f"{r['test_metrics']['R2']:.3f}"}
                            for r in sorted(done, key=lambda r: r["test_metrics"]["RMSE"])])
        sp = exps[-1]["split_pct"]
        sections.append({"title": "Model evaluation results", "table": tbl,
                         "notes": [f"Experiment {exps[-1]['id']}: chronological split {sp[0]}/{sp[1]}/{sp[2]} "
                                   "(train/validation/test), metrics on the test split in kWh."]})
    else:
        sections.append({"title": "Model evaluation results", "notes": ["No completed Model Lab experiment for this dataset."]})

result = detect_statistical(daily, "daily", threshold=3.0)
an = anomaly_table(result)
an = an[(an["timestamp"] >= start) & (an["timestamp"] <= end)]
if "Anomalies" in include:
    rows = [("Method", "Statistical threshold (robust z-score), medium sensitivity, daily"),
            ("Unusual days flagged", f"{len(an)}"),
            ("High severity", f"{int((an['severity'] == 'High').sum())}")]
    tbl = None
    if len(an):
        tbl = pd.DataFrame({"Date": an["timestamp"].dt.strftime("%d %b %Y"), "Severity": an["severity"],
                            f"Observed ({unit})": [fmt_energy(v, unit).split(" ")[0] for v in an["observed"]],
                            f"Expected ({unit})": [fmt_energy(v, unit).split(" ")[0] for v in an["expected"]],
                            "Deviation": [f"{v:+.0f}%" for v in an["deviation_pct"]]}).head(10)
    sections.append({"title": "Anomaly summary", "rows": rows, "table": tbl,
                     "notes": ["Anomalies are signals for investigation, not confirmed faults."]})

if "Insights" in include:
    notes = []
    wk = period["y"][period.index.dayofweek < 5].mean()
    we = period["y"][period.index.dayofweek >= 5].mean()
    if wk and not np.isnan(we):
        notes.append(f"Weekend days averaged {we / wk:.0%} of weekday consumption.")
    if not np.isnan(change):
        notes.append(f"Consumption {'increased' if change > 0 else 'decreased'} by {abs(change):.1f}% compared with the previous "
                     f"{len(period)} days ({fmt_money(abs(k['cost'] - kp['cost']), cfg['currency'])} estimated cost difference).")
    temp = [c for c in series.columns if "temp" in c.lower()]
    if temp:
        corr = period["y"].corr(period[temp[0]])
        if not np.isnan(corr):
            notes.append(f"Daily consumption and temperature correlation: {corr:+.2f}.")
    if len(an):
        notes.append(f"{len(an)} unusual day(s) should be reviewed with facility staff.")
    sections.append({"title": "Energy insights", "notes": notes or ["Not enough data for insights in this period."]})

report = {"title": title, "meta": meta, "sections": sections,
          "demo_notice": "This report is based on a synthetic dataset generated by EnergyIntel and does not describe a real site."
          if is_demo else None}

# ---------------- Preview ----------------
section_header("Report preview", "This is what the PDF will contain")
html = [f'<div class="ei-report"><div class="ei-eyebrow">ENERGYINTEL · ENERGY INTELLIGENCE REPORT</div>'
        f'<h2>{escape(title)}</h2><div class="muted">{" · ".join(f"{escape(k)}: {escape(str(v))}" for k, v in meta.items())}</div>']
if report["demo_notice"]:
    html.append(f'<div class="ei-banner demo" style="margin-top:1rem"><div><b>Demonstration data.</b> {escape(report["demo_notice"])}</div></div>')
for s in sections:
    html.append(f"<h4>{escape(s['title'])}</h4>")
    if s.get("rows"):
        html.append("<table>" + "".join(f"<tr><td class='muted' style='width:45%'>{escape(a)}</td><td><b>{escape(str(b))}</b></td></tr>"
                                        for a, b in s["rows"]) + "</table>")
    if s.get("table") is not None and not s["table"].empty:
        t = s["table"]
        html.append("<table style='margin-top:.5rem'><tr>" + "".join(f"<th>{escape(str(c))}</th>" for c in t.columns) + "</tr>"
                    + "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in t.itertuples(index=False))
                    + "</table>")
    for n in s.get("notes", []):
        html.append(f"<p class='muted' style='margin:.5rem 0 0'>{escape(n)}</p>")
html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

# ---------------- Export ----------------
st.write("")
slug = proj["name"].lower().replace(" ", "_")
a, b, _ = st.columns([1, 1, 2])
a.download_button("Download CSV summary", report_rows(report).to_csv(index=False).encode("utf-8"),
                  f"energyintel_report_{slug}.csv", "text/csv", width="stretch", icon=":material/table:")
try:
    pdf = build_pdf(report)
    b.download_button("Download PDF report", pdf, f"energyintel_report_{slug}.pdf", "application/pdf",
                      type="primary", width="stretch", icon=":material/picture_as_pdf:")
except Exception as exc:  # keep the page usable if PDF rendering fails
    b.error(f"PDF could not be generated: {exc}")

footer()
