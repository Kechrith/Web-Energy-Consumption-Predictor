"""Dataset validation: column suggestions, timestamp/target checks, quality summaries."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TIME_HINTS = ("timestamp", "datetime", "date", "time", "period", "ds")
TARGET_HINTS = ("consumption", "energy", "kwh", "usage", "load", "demand", "power", "y")
WEATHER_HINTS = ("temp", "humid", "weather", "rain", "solar", "irradiance", "wind", "dew", "cloud")


@dataclass
class ValidationReport:
    checks: list = field(default_factory=list)   # dicts: status, title, detail
    errors: list = field(default_factory=list)   # blocking messages
    frequency: str = "unknown"                   # hourly | daily | sub-hourly | irregular | unknown
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, status: str, title: str, detail: str = "") -> None:
        self.checks.append({"status": status, "title": title, "detail": detail})
        if status == "error":
            self.errors.append(f"{title}: {detail}")


def parse_datetimes(values: pd.Series) -> pd.Series:
    """Parse dates robustly, trying month-first and day-first orders (e.g. 13/01/2025).

    Keeps whichever order parses more values; on a tie, the one spanning the shorter
    period (ambiguous day-first dates read month-first scatter across the year).
    """
    if pd.api.types.is_datetime64_any_dtype(values):
        return pd.Series(values)
    if pd.api.types.is_numeric_dtype(values):
        return pd.Series(pd.NaT, index=values.index)
    text = values.astype("string").str.strip()
    a = pd.to_datetime(text, errors="coerce", format="mixed")
    b = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=True)
    na, nb = a.notna().sum(), b.notna().sum()
    if na != nb:
        return a if na > nb else b
    span = lambda s: (s.max() - s.min()) if s.notna().any() else pd.Timedelta(0)
    return b if span(b) < span(a) else a


def suggest_columns(df: pd.DataFrame) -> dict:
    """Guess the timestamp, target and weather columns from names and dtypes."""
    cols = list(df.columns)
    lower = {c: str(c).lower() for c in cols}

    time_col = next((c for c in cols if lower[c] in TIME_HINTS), None)
    if time_col is None:
        time_col = next((c for c in cols if any(h in lower[c] for h in TIME_HINTS)), None)
    if time_col is None:
        time_col = next((c for c in cols if pd.api.types.is_datetime64_any_dtype(df[c])), None)

    numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and c != time_col]
    target_col = next((c for c in numeric if any(h in lower[c] for h in TARGET_HINTS if h != "y")), None)
    if target_col is None:
        target_col = next((c for c in numeric if lower[c] == "y"), numeric[0] if numeric else None)

    weather = [c for c in numeric if c != target_col and any(h in lower[c] for h in WEATHER_HINTS)]
    return {"time_col": time_col, "target_col": target_col, "weather_cols": weather}


def infer_frequency(ts: pd.Series) -> str:
    ts = parse_datetimes(pd.Series(ts)).dropna().sort_values()
    if len(ts) < 3:
        return "unknown"
    step = ts.diff().dropna().median()
    if step <= pd.Timedelta(minutes=59):
        return "sub-hourly"
    if step <= pd.Timedelta(hours=1, minutes=5):
        return "hourly"
    if pd.Timedelta(hours=23) <= step <= pd.Timedelta(hours=25):
        return "daily"
    return "irregular"


def validate_dataset(df: pd.DataFrame, time_col: str | None, target_col: str | None,
                     weather_cols: list | None = None) -> ValidationReport:
    """Validate a dataset against the chosen column mapping. Never raises."""
    rep = ValidationReport()
    if df is None or df.empty:
        rep.add("error", "Dataset is empty", "The file contains no rows.")
        return rep

    rep.add("ok", f"{len(df):,} rows × {len(df.columns)} columns", "File parsed successfully.")

    # --- timestamp ---
    if not time_col or time_col not in df.columns:
        rep.add("error", "Timestamp column missing", "Select the column that contains the date or time of each reading.")
    else:
        parsed = parse_datetimes(df[time_col])
        bad = int(parsed.isna().sum())
        share = bad / len(df)
        if share > 0.2:
            rep.add("error", "Timestamps could not be parsed",
                    f"{bad:,} of {len(df):,} values in '{time_col}' are not valid dates. Check the column or date format.")
        elif bad:
            rep.add("warn", "Some timestamps are invalid", f"{bad:,} rows will be dropped because '{time_col}' is not a valid date.")
        else:
            rep.add("ok", "All timestamps are valid", f"Column '{time_col}' parsed as dates.")

        valid = parsed.dropna()
        if len(valid):
            rep.start, rep.end = valid.min(), valid.max()
            rep.frequency = infer_frequency(valid)
            dups = int(valid.duplicated().sum())
            if dups:
                rep.add("warn", "Duplicate timestamps", f"{dups:,} repeated timestamps will be averaged when the series is prepared.")
            if not valid.is_monotonic_increasing:
                rep.add("warn", "Rows are not in time order", "Rows will be sorted chronologically before analysis.")
            if rep.frequency in ("hourly", "daily"):
                step = pd.Timedelta(hours=1) if rep.frequency == "hourly" else pd.Timedelta(days=1)
                expected = int((rep.end - rep.start) / step) + 1
                missing = max(0, expected - valid.nunique())
                if missing:
                    rep.add("warn", "Gaps in the time series",
                            f"{missing:,} expected {rep.frequency} periods have no reading ({missing / expected:.1%}). They will be interpolated.")
                else:
                    rep.add("ok", f"Regular {rep.frequency} series", f"{rep.start:%d %b %Y} → {rep.end:%d %b %Y}, no gaps.")
            elif rep.frequency == "sub-hourly":
                rep.add("ok", "Sub-hourly readings detected", "Readings will be aggregated to hourly totals.")
            else:
                rep.add("warn", "Irregular time spacing", "Readings will be aggregated to daily totals.")
            if len(valid.dt.normalize().unique()) < 14:
                rep.add("error", "Not enough history", "At least 14 days of data are needed for forecasting and anomaly detection.")

    # --- target ---
    if not target_col or target_col not in df.columns:
        rep.add("error", "Consumption column missing", "Select the numeric column with energy consumption (e.g. kWh).")
    elif target_col == time_col:
        rep.add("error", "Columns overlap", "The consumption column must be different from the timestamp column.")
    else:
        values = pd.to_numeric(df[target_col], errors="coerce")
        bad = int(values.isna().sum())
        if bad / len(df) > 0.5:
            rep.add("error", "Consumption values are not numeric", f"More than half of '{target_col}' cannot be read as numbers.")
        elif bad:
            rep.add("warn", "Missing consumption values", f"{bad:,} rows ({bad / len(df):.1%}) have no usable value in '{target_col}'.")
        else:
            rep.add("ok", "Consumption values are complete", f"All values in '{target_col}' are numeric.")
        neg = int((values < 0).sum())
        if neg:
            rep.add("warn", "Negative consumption values", f"{neg:,} values are below zero — check for meter resets or export readings.")
        if values.notna().sum() and values.std(skipna=True) == 0:
            rep.add("warn", "Constant consumption", "The consumption column has no variation; forecasts will not be meaningful.")

    # --- weather ---
    for col in weather_cols or []:
        if col not in df.columns:
            rep.add("warn", f"Weather column '{col}' not found", "It will be ignored.")
            continue
        miss = pd.to_numeric(df[col], errors="coerce").isna().mean()
        if miss > 0.3:
            rep.add("warn", f"Weather feature '{col}' is sparse", f"{miss:.0%} missing — it may weaken model results.")

    dup_rows = int(df.duplicated().sum())
    if dup_rows:
        rep.add("warn", "Duplicate rows", f"{dup_rows:,} fully identical rows found.")
    return rep


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            kind = "Numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            kind = "Datetime"
        else:
            sample = s.dropna().astype(str).head(50)
            parsed = parse_datetimes(sample) if len(sample) else sample
            kind = "Datetime (text)" if len(sample) and parsed.notna().mean() > 0.9 else "Categorical / text"
        rows.append({
            "Column": str(c),
            "Detected type": kind,
            "Pandas dtype": str(s.dtype),
            "Missing": int(s.isna().sum()),
            "Missing %": round(float(s.isna().mean() * 100), 1),
            "Unique": int(s.nunique(dropna=True)),
        })
    return pd.DataFrame(rows)


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    num = df.select_dtypes(include=np.number)
    if num.empty:
        return pd.DataFrame()
    desc = num.describe().T
    desc = desc.rename(columns={"count": "Count", "mean": "Mean", "std": "Std dev", "min": "Min",
                                "25%": "Q1", "50%": "Median", "75%": "Q3", "max": "Max"})
    return desc.round(2).reset_index(names="Column")


def categorical_summary(df: pd.DataFrame) -> pd.DataFrame:
    cat = df.select_dtypes(exclude=[np.number, "datetime", "datetimetz"])
    rows = []
    for c in cat.columns:
        vc = cat[c].astype(str).value_counts(dropna=True)
        rows.append({
            "Column": str(c),
            "Unique values": int(cat[c].nunique(dropna=True)),
            "Most frequent": vc.index[0] if len(vc) else "—",
            "Frequency": int(vc.iloc[0]) if len(vc) else 0,
        })
    return pd.DataFrame(rows)
