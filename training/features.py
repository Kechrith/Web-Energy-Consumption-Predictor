from datetime import datetime

FEATURES = (
    ["lights"]
    + [f"T{i}" for i in range(1, 10)]
    + [f"RH_{i}" for i in range(1, 10)]
    + ["T_out", "Press_mm_hg", "RH_out", "Windspeed", "Visibility", "Tdewpoint"]
    + ["hour", "dayofweek", "is_weekend"]
)

def time_features(ts: datetime) -> dict:
    """Same time features as the notebook's feature engineering step."""
    dayofweek = ts.weekday()  # 0 = Monday, matches pandas .dt.dayofweek
    return {"hour": ts.hour, "dayofweek": dayofweek, "is_weekend": int(dayofweek >= 5)}