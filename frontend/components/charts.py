"""Plotly chart builders with a consistent EnergyIntel look."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.styles import COLORS
from utils.formatting import unit_factor

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
                 "toImageButtonOptions": {"format": "png", "scale": 2}}


def _layout(fig: go.Figure, height: int = 340, unit: str = "kWh", y_title: str | None = None,
            legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#334155"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=COLORS["border"], font_size=12),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color="#475569")),
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["border"], tickfont=dict(color=COLORS["muted"]), ticks="")
    fig.update_yaxes(gridcolor="#EEF2F6", zeroline=False, tickfont=dict(color=COLORS["muted"]),
                     title=dict(text=y_title if y_title is not None else unit, font=dict(size=11, color=COLORS["muted"])),
                     separatethousands=True)
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, config=PLOTLY_CONFIG, key=key, width="stretch")


def _band(fig: go.Figure, x, lower, upper, color: str, name: str) -> None:
    fig.add_trace(go.Scatter(x=x, y=upper, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=lower, mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor=color, name=name, hoverinfo="skip"))


def consumption_chart(daily: pd.DataFrame, unit: str, rolling: bool = True, height: int = 330) -> go.Figure:
    f = unit_factor(unit)
    fig = go.Figure()
    y = daily["y"] * f
    fig.add_trace(go.Scatter(x=daily.index, y=y, name="Daily consumption", mode="lines",
                             line=dict(color=COLORS["blue"], width=2),
                             fill="tozeroy", fillcolor="rgba(37,99,235,0.06)",
                             hovertemplate="%{y:,.1f} " + unit + "<extra></extra>"))
    if rolling and len(daily) >= 7:
        fig.add_trace(go.Scatter(x=daily.index, y=y.rolling(7, min_periods=1).mean(), name="7-day average",
                                 mode="lines", line=dict(color=COLORS["navy"], width=1.5, dash="dot"),
                                 hovertemplate="%{y:,.1f} " + unit + "<extra></extra>"))
    return _layout(fig, height, unit)


def forecast_chart(history: pd.Series, forecast: pd.DataFrame, unit: str, height: int = 360,
                   show_interval: bool = True, interval_label: str = "Prediction interval") -> go.Figure:
    f = unit_factor(unit)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.index, y=history * f, name="Historical", mode="lines",
                             line=dict(color=COLORS["blue"], width=1.8),
                             hovertemplate="%{y:,.1f} " + unit + "<extra>Historical</extra>"))
    if show_interval and "lower" in forecast:
        _band(fig, forecast["timestamp"], forecast["lower"] * f, forecast["upper"] * f,
              "rgba(22,163,74,0.14)", interval_label)
    # Connect the forecast line to the last observed point for visual continuity.
    x = [history.index[-1], *forecast["timestamp"]]
    yv = [history.iloc[-1] * f, *(forecast["forecast"] * f)]
    fig.add_trace(go.Scatter(x=x, y=yv, name="Forecast", mode="lines",
                             line=dict(color=COLORS["green"], width=2.2, dash="dash"),
                             hovertemplate="%{y:,.1f} " + unit + "<extra>Forecast</extra>"))
    fig.add_vline(x=history.index[-1], line=dict(color=COLORS["slate"], width=1, dash="dot"))
    fig.add_annotation(x=history.index[-1], y=1, yref="paper", text="Forecast starts", showarrow=False,
                       xanchor="left", xshift=6, font=dict(size=10, color=COLORS["muted"]))
    return _layout(fig, height, unit)


def actual_vs_predicted(frame: pd.DataFrame, unit: str, height: int = 300) -> go.Figure:
    f = unit_factor(unit)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["actual"] * f, name="Actual", mode="lines",
                             line=dict(color=COLORS["navy"], width=2),
                             hovertemplate="%{y:,.1f} " + unit + "<extra>Actual</extra>"))
    fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["predicted"] * f, name="Predicted", mode="lines",
                             line=dict(color=COLORS["green"], width=2, dash="dash"),
                             hovertemplate="%{y:,.1f} " + unit + "<extra>Predicted</extra>"))
    return _layout(fig, height, unit)


def anomaly_chart(result: pd.DataFrame, unit: str, height: int = 380, show_expected: bool = True) -> go.Figure:
    f = unit_factor(unit)
    fig = go.Figure()
    if show_expected:
        fig.add_trace(go.Scatter(x=result["timestamp"], y=result["expected"] * f, name="Expected", mode="lines",
                                 line=dict(color=COLORS["slate"], width=1.3, dash="dot"),
                                 hovertemplate="%{y:,.1f} " + unit + "<extra>Expected</extra>"))
    fig.add_trace(go.Scatter(x=result["timestamp"], y=result["observed"] * f, name="Observed", mode="lines",
                             line=dict(color=COLORS["blue"], width=1.6),
                             hovertemplate="%{y:,.1f} " + unit + "<extra>Observed</extra>"))
    sev_style = {"High": (COLORS["red"], 11), "Medium": ("#EA580C", 9), "Low": ("#CA8A04", 7)}
    for sev, (color, size) in sev_style.items():
        pts = result[result["severity"] == sev]
        if len(pts):
            fig.add_trace(go.Scatter(
                x=pts["timestamp"], y=pts["observed"] * f, mode="markers", name=f"{sev} severity",
                marker=dict(color=color, size=size, line=dict(color="#FFFFFF", width=1.5)),
                customdata=np.stack([pts["expected"] * f, pts["deviation_pct"]], axis=-1),
                hovertemplate="Observed %{y:,.1f} " + unit + "<br>Expected %{customdata[0]:,.1f}"
                              "<br>Deviation %{customdata[1]:+.1f}%<extra>" + sev + "</extra>",
            ))
    return _layout(fig, height, unit)


def weekday_hour_heatmap(series: pd.DataFrame, unit: str, height: int = 300) -> go.Figure:
    f = unit_factor(unit)
    d = series[["y"]].copy()
    d["dow"] = d.index.dayofweek
    d["hour"] = d.index.hour
    pivot = d.pivot_table(index="dow", columns="hour", values="y", aggfunc="mean").reindex(range(7))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = go.Figure(go.Heatmap(
        z=pivot.to_numpy() * f, x=[f"{h:02d}:00" for h in pivot.columns], y=days,
        colorscale=[[0, "#F1F5F9"], [0.45, "#93C5FD"], [0.8, "#2563EB"], [1, "#10243A"]],
        colorbar=dict(title=dict(text=unit, side="right"), thickness=10, outlinewidth=0),
        hovertemplate="%{y} %{x}<br>Avg %{z:,.2f} " + unit + "<extra></extra>", xgap=1, ygap=1,
    ))
    fig = _layout(fig, height, unit, y_title="", legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(dtick=6, tickangle=0)
    return fig


def weekday_bar(daily: pd.DataFrame, unit: str, height: int = 300) -> go.Figure:
    f = unit_factor(unit)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    avg = daily["y"].groupby(daily.index.dayofweek).mean().reindex(range(7)) * f
    colors = [COLORS["blue"] if v < avg.max() else COLORS["navy"] for v in avg]
    fig = go.Figure(go.Bar(x=days, y=avg, marker_color=colors, marker_line_width=0,
                           hovertemplate="%{x}: %{y:,.1f} " + unit + "<extra></extra>"))
    fig = _layout(fig, height, unit, legend=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    return fig


def model_comparison(df: pd.DataFrame, metric: str, height: int = 300, lower_is_better: bool = True) -> go.Figure:
    d = df.dropna(subset=[metric]).sort_values(metric, ascending=not lower_is_better)
    best = d[metric].min() if lower_is_better else d[metric].max()
    colors = [COLORS["green"] if v == best else "#CBD5E1" for v in d[metric]]
    fig = go.Figure(go.Bar(x=d[metric], y=d["Model"], orientation="h", marker_color=colors,
                           text=[f"{v:,.2f}" for v in d[metric]], textposition="outside",
                           hovertemplate="%{y}: %{x:,.3f}<extra></extra>", cliponaxis=False))
    fig = _layout(fig, height, "", y_title="", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.4)
    fig.update_xaxes(showgrid=True, gridcolor="#EEF2F6", title=dict(text=metric, font=dict(size=11)))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return fig


def importance_chart(imp: pd.DataFrame, height: int = 280) -> go.Figure:
    d = imp.head(10).iloc[::-1]
    fig = go.Figure(go.Bar(x=d["importance"] * 100, y=d["feature"], orientation="h",
                           marker_color=COLORS["blue"], text=[f"{v:.0%}" for v in d["importance"]],
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
    fig = _layout(fig, height, "", y_title="", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    fig.update_xaxes(title=dict(text="Relative importance (%)", font=dict(size=11)), showgrid=True, gridcolor="#EEF2F6")
    return fig


def missing_values_chart(profile: pd.DataFrame, height: int = 260) -> go.Figure:
    d = profile.sort_values("Missing %")
    colors = [COLORS["red"] if v > 20 else COLORS["amber"] if v > 0 else COLORS["green"] for v in d["Missing %"]]
    fig = go.Figure(go.Bar(x=d["Missing %"], y=d["Column"], orientation="h", marker_color=colors,
                           text=[f"{v:.1f}%" for v in d["Missing %"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}% missing<extra></extra>"))
    fig = _layout(fig, height, "", y_title="", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    fig.update_xaxes(range=[0, max(100, float(d["Missing %"].max()) * 1.15)],
                     title=dict(text="Missing values (%)", font=dict(size=11)), showgrid=True, gridcolor="#EEF2F6")
    return fig


def distribution_chart(values: pd.Series, name: str, height: int = 260) -> go.Figure:
    fig = go.Figure(go.Histogram(x=values.dropna(), nbinsx=40, marker_color=COLORS["blue"], opacity=0.85,
                                 hovertemplate="%{x}<br>%{y} rows<extra></extra>"))
    fig = _layout(fig, height, "", y_title="Rows", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.05)
    fig.update_xaxes(title=dict(text=name, font=dict(size=11)))
    return fig


def split_timeline(splits: dict, height: int = 110) -> go.Figure:
    """Horizontal timeline of chronological train / validation / test windows."""
    colors = {"train": COLORS["blue"], "val": COLORS["amber"], "test": COLORS["green"]}
    names = {"train": "Train", "val": "Validation", "test": "Test"}
    fig = go.Figure()
    for k, (s, e) in splits.items():
        fig.add_trace(go.Bar(
            x=[(pd.Timestamp(e) - pd.Timestamp(s)).total_seconds() * 1000], y=["Split"], base=[pd.Timestamp(s)],
            orientation="h", marker_color=colors[k], name=names[k], width=0.5,
            hovertemplate=f"{names[k]}: {pd.Timestamp(s):%d %b %Y} → {pd.Timestamp(e):%d %b %Y}<extra></extra>",
        ))
    fig = _layout(fig, height, "", y_title="")
    fig.update_layout(barmode="overlay", hovermode="closest", margin=dict(l=8, r=8, t=28, b=8))
    fig.update_yaxes(visible=False)
    fig.update_xaxes(type="date")
    return fig
