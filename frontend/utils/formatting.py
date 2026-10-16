"""Number and unit formatting helpers."""

import math

import pandas as pd


def unit_factor(unit: str) -> float:
    """Multiplier to convert kWh values into the display unit."""
    return 0.001 if unit == "MWh" else 1.0


def fmt_energy(value_kwh: float, unit: str = "kWh", decimals: int | None = None) -> str:
    if value_kwh is None or (isinstance(value_kwh, float) and math.isnan(value_kwh)):
        return "—"
    value = value_kwh * unit_factor(unit)
    if decimals is None:
        decimals = 2 if unit == "MWh" else 0
    return f"{value:,.{decimals}f} {unit}"


def fmt_money(value: float, currency: str = "USD") -> str:
    symbol = {"USD": "$", "KHR": "៛", "EUR": "€"}.get(currency, "")
    if currency == "KHR":
        return f"{symbol}{value:,.0f}"
    return f"{symbol}{value:,.2f}" if value < 10_000 else f"{symbol}{value:,.0f}"


def fmt_pct(value: float, signed: bool = True, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:+.{decimals}f}%" if signed else f"{value:.{decimals}f}%"


def fmt_date(ts, with_time: bool = False) -> str:
    ts = pd.Timestamp(ts)
    return ts.strftime("%d %b %Y, %H:%M") if with_time else ts.strftime("%d %b %Y")


def time_ago(ts) -> str:
    delta = pd.Timestamp.now() - pd.Timestamp(ts)
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    days = secs // 86400
    return "yesterday" if days == 1 else f"{days} days ago"
