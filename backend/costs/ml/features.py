import pandas as pd


def daily_series_dataframe(cost_records_qs) -> pd.DataFrame:
    """Aggregate a CostRecord queryset into a daily total-cost time series
    indexed by date, with one row per calendar day (missing days filled
    with 0) -- the shape both the anomaly detector and the forecaster need.
    """
    rows = list(cost_records_qs.values("date", "amount"))
    if not rows:
        return pd.DataFrame(columns=["date", "amount"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    daily = df.groupby("date", as_index=False)["amount"].sum()

    full_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = (
        daily.set_index("date")
        .reindex(full_range, fill_value=0.0)
        .rename_axis("date")
        .reset_index()
    )
    return daily


def build_anomaly_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Engineer features for Isolation Forest from a daily cost series:
    the raw amount, day-of-week, rolling mean/std, and deviation from the
    trailing 7-day rolling mean (the signal that actually distinguishes a
    genuine cost spike from normal week-to-week variation).
    """
    out = daily.copy()
    out["dayofweek"] = out["date"].dt.dayofweek
    out["rolling_mean_7"] = out["amount"].rolling(7, min_periods=1).mean()
    out["rolling_std_7"] = out["amount"].rolling(7, min_periods=1).std().fillna(0.0)
    out["deviation"] = out["amount"] - out["rolling_mean_7"]
    out["pct_change"] = out["amount"].pct_change().replace([float("inf"), float("-inf")], 0).fillna(0.0)
    return out
