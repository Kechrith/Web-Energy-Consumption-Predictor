"""Dashboard overview: KPIs, consumption, short-term forecast, peaks, anomalies and insights."""

import numpy as np
import pandas as pd
import streamlit as st

from components import charts
from components.layout import page_context
from components.metric_cards import badge, footer, item_list, kpi_card, section_header
from services.anomaly_service import anomaly_table, detect_statistical
from services.data_service import period_kpis, previous_period
from services.forecast_service import LOCAL_MODELS, run_forecast
from services.state import dataset_selector, prepared, settings
from utils.formatting import fmt_date, fmt_energy, fmt_money, fmt_pct

proj, ds = page_context("Dashboard", "A snapshot of consumption, cost, upcoming demand and unusual usage for the active project.")
cfg = settings()
unit = cfg["unit"]

# ---------- Filters ----------
f1, f2, f3 = st.columns([1.3, 1.4, 1], vertical_alignment="bottom")
with f1:
    ds = dataset_selector("Dataset", key="dash_ds")
series, daily, freq = prepared(ds)
if daily.empty:
    st.error("The selected dataset has no usable rows. Check the column mapping on the Datasets page.")
    st.stop()

min_d, max_d = daily.index.min().date(), daily.index.max().date()
default_start = max(min_d, max_d - pd.Timedelta(days=29))
with f2:
    picked = st.date_input("Date range", value=(default_start, max_d), min_value=min_d, max_value=max_d,
                           format="DD/MM/YYYY", help="KPIs and charts use this period. The change is compared with the period of equal length immediately before.")
with f3:
    quick = st.segmented_control("Quick range", ["7D", "30D", "90D", "All"], default=None, key="dash_quick")

if quick:
    days = {"7D": 7, "30D": 30, "90D": 90}.get(quick)
    start, end = (pd.Timestamp(min_d) if days is None else pd.Timestamp(max_d) - pd.Timedelta(days=days - 1)), pd.Timestamp(max_d)
elif isinstance(picked, (tuple, list)) and len(picked) == 2:
    start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
else:
    st.info("Select an end date to complete the range.")
    st.stop()
start = max(start, pd.Timestamp(min_d))

period = daily.loc[start:end]
prev = previous_period(daily, start, end)
k = period_kpis(period, cfg["tariff"])
kp = period_kpis(prev, cfg["tariff"]) if len(prev) == len(period) else {}
change = (k["total"] - kp["total"]) / kp["total"] * 100 if kp.get("total") else np.nan

# ---------- KPIs ----------
st.write("")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("Total consumption", fmt_energy(k["total"], unit), f"{k['days']} days selected", icon_name="zap", tone="blue")
with c2:
    avg_change = (k["avg"] - kp["avg"]) / kp["avg"] * 100 if kp.get("avg") else np.nan
    kpi_card("Average daily", fmt_energy(k["avg"], unit, 1 if unit == "kWh" else 2), "per day",
             delta=fmt_pct(avg_change) if not np.isnan(avg_change) else "", delta_tone="bad" if avg_change > 0 else "good",
             icon_name="activity", tone="navy")
with c3:
    kpi_card("Peak day", fmt_energy(k["peak"], unit), f"on {fmt_date(k['peak_date'])}", icon_name="gauge", tone="amber")
with c4:
    kpi_card("Estimated cost", fmt_money(k["cost"], cfg["currency"]),
             f"at {cfg['tariff']:.3f} {cfg['currency']}/kWh (estimate)", icon_name="dollar", tone="green",
             help_text="Flat tariff from Settings. Real bills may include demand charges and time-of-use rates.")
with c5:
    if np.isnan(change):
        kpi_card("vs previous period", "—", "Not enough earlier data", icon_name="trending-up", tone="navy")
    else:
        kpi_card("vs previous period", fmt_pct(change), f"vs {fmt_date(prev.index.min())} – {fmt_date(prev.index.max())}",
                 icon_name="trending-up" if change >= 0 else "trending-down", tone="red" if change > 0 else "green",
                 delta="higher use" if change > 0 else "lower use", delta_tone="bad" if change > 0 else "good")

# ---------- Consumption + forecast ----------
model = cfg["default_model"] if cfg["default_model"] in LOCAL_MODELS else "Seasonal Naive"
try:
    fc = run_forecast(daily, "daily", model, 7, interval=0.9)
except ValueError as exc:
    fc = None
    fc_error = str(exc)

left, right = st.columns([1.65, 1])
with left, st.container(border=True):
    section_header("Historical consumption", f"Daily totals, {fmt_date(start)} – {fmt_date(end)}")
    charts.show(charts.consumption_chart(period, unit), key="dash_hist")
with right, st.container(border=True):
    section_header("Next 7 days", f"{model} · computed locally", badge("Baseline", "info"))
    if fc:
        charts.show(charts.forecast_chart(daily["y"].tail(21), fc["forecast"], unit, height=250,
                                          interval_label="90% interval"), key="dash_fc")
        nxt = fc["forecast"]
        pk = nxt.loc[nxt["forecast"].idxmax()]
        st.caption(f"Expected total **{fmt_energy(nxt['forecast'].sum(), unit)}** · busiest day "
                   f"**{pd.Timestamp(pk['timestamp']):%a %d %b}**. Baseline forecast — open Forecasting for other models.")
    else:
        st.warning(fc_error)

left, right = st.columns([1.65, 1])
with left, st.container(border=True):
    if fc:
        m = fc["metrics"]
        section_header("Actual vs predicted", f"Backtest of the last {len(fc['backtest'])} days the model did not see")
        charts.show(charts.actual_vs_predicted(fc["backtest"], unit, height=260), key="dash_avp")
        mape = f"MAPE {m['MAPE']:.1f}%" if not np.isnan(m["MAPE"]) else "MAPE n/a"
        st.caption(f"{model}: MAE {fmt_energy(m['MAE'], unit, 1)} · {mape}. Real error on held-out data"
                   f"{' (synthetic dataset)' if ds['source'] == 'demo' else ''}.")
with right, st.container(border=True):
    if freq == "hourly":
        section_header("Peak-demand periods", "Average consumption by weekday and hour")
        charts.show(charts.weekday_hour_heatmap(series.loc[start:end + pd.Timedelta(hours=23)], unit, height=290), key="dash_heat")
    else:
        section_header("Peak-demand periods", "Average consumption by weekday")
        charts.show(charts.weekday_bar(period, unit, height=290), key="dash_week")

# ---------- Alerts + insights ----------
result = detect_statistical(daily, "daily", threshold=3.0)
alerts = anomaly_table(result)
alerts = alerts[alerts["timestamp"] >= daily.index.max() - pd.Timedelta(days=60)].sort_values("timestamp", ascending=False).head(4)

left, right = st.columns(2)
with left:
    section_header("Recent anomaly alerts", "Last 60 days · statistical threshold, medium sensitivity")
    if alerts.empty:
        item_list([{"title": "No unusual days detected", "icon": "check", "tone": "green",
                    "body": "Daily consumption stayed within the expected range for the last 60 days."}])
    else:
        item_list([{
            "title": f"{pd.Timestamp(r.timestamp):%a %d %b %Y} · {r.severity} severity",
            "body": f"{fmt_energy(r.observed, unit)} observed vs {fmt_energy(r.expected, unit)} expected "
                    f"({r.deviation_pct:+.0f}%). Worth investigating — not proof of a fault.",
            "icon": "alert", "tone": "red" if r.severity == "High" else "amber",
        } for r in alerts.itertuples()])
    st.page_link("pages/anomaly_detection.py", label="Investigate anomalies", icon=":material/arrow_forward:")

insights = []
weekday = period["y"][period.index.dayofweek < 5].mean()
weekend = period["y"][period.index.dayofweek >= 5].mean()
if weekday and not np.isnan(weekend):
    ratio = weekend / weekday
    insights.append({"title": f"Weekends use {ratio:.0%} of a typical weekday",
                     "body": "A high weekend share can point to equipment that is not scheduled off." if ratio > 0.6
                     else "Weekend load drops as expected for an occupancy-driven site.", "icon": "calendar", "tone": "blue"})
if freq == "hourly":
    hourly = series.loc[start:end + pd.Timedelta(hours=23), "y"]
    by_hour = hourly.groupby(hourly.index.hour).mean()
    night = by_hour.loc[[0, 1, 2, 3, 4]].mean()
    insights.append({"title": f"Demand peaks around {int(by_hour.idxmax()):02d}:00",
                     "body": f"Overnight base load is {night / by_hour.mean():.0%} of the daily average. "
                             "Reducing after-hours load is often the cheapest saving.", "icon": "clock", "tone": "navy"})
temp_cols = [c for c in series.columns if "temp" in c.lower()]
if temp_cols and len(period) > 10:
    corr = period["y"].corr(period[temp_cols[0]])
    if not np.isnan(corr):
        insights.append({"title": f"Temperature correlation: {corr:+.2f}",
                         "body": "Hotter days drive noticeably higher use — cooling efficiency matters." if corr > 0.3
                         else "Consumption is only weakly linked to temperature in this period.", "icon": "activity", "tone": "amber"})
if not np.isnan(change):
    insights.append({"title": f"Consumption {'rose' if change > 0 else 'fell'} {abs(change):.1f}% vs the previous period",
                     "body": f"Estimated cost impact: {fmt_money(abs(k['cost'] - kp['cost']), cfg['currency'])} "
                             f"{'more' if change > 0 else 'less'} than the period before.", "icon": "lightbulb", "tone": "green"})
with right:
    section_header("Energy insights", "Generated from the selected period")
    item_list(insights or [{"title": "Not enough data for insights", "body": "Select a longer date range.", "icon": "info"}])

footer()
