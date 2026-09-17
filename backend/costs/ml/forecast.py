import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from django.conf import settings

from costs.models import CostRecord, Forecast

from .features import daily_series_dataframe

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 14


def _forecast_with_prophet(daily: pd.DataFrame, horizon_days: int):
    from prophet import Prophet

    df = daily.rename(columns={"date": "ds", "amount": "y"})
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.9,
    )
    model.fit(df)
    future = model.make_future_dataframe(periods=horizon_days)
    forecast = model.predict(future)
    tail = forecast.tail(horizon_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    tail = tail.rename(columns={"ds": "date", "yhat": "predicted", "yhat_lower": "lower", "yhat_upper": "upper"})
    tail[["predicted", "lower", "upper"]] = tail[["predicted", "lower", "upper"]].clip(lower=0)
    return tail, "prophet"


def _forecast_naive_seasonal(daily: pd.DataFrame, horizon_days: int):
    """Fallback used if Prophet isn't available/fails to fit (e.g. no
    internet access to build its Stan backend in a locked-down environment).
    Linear trend over the day index plus a per-weekday seasonal factor
    learned from history, with a residual-std based confidence band --
    the same shape of output as the Prophet path, just simpler.
    """
    y = daily["amount"].values
    n = len(y)
    x = np.arange(n)

    slope, intercept = np.polyfit(x, y, 1)
    trend = slope * x + intercept

    weekday = daily["date"].dt.dayofweek.values
    residual_after_trend = y - trend
    seasonal_factor = np.ones(7)
    for wd in range(7):
        mask = weekday == wd
        if mask.any():
            baseline = trend[mask].mean() or 1.0
            seasonal_factor[wd] = 1 + (residual_after_trend[mask].mean() / baseline)

    fitted = trend * seasonal_factor[weekday]
    residual_std = float(np.std(y - fitted)) or (float(np.mean(y)) * 0.1 + 1)

    last_date = daily["date"].iloc[-1]
    rows = []
    for h in range(1, horizon_days + 1):
        future_x = n - 1 + h
        future_date = last_date + timedelta(days=h)
        predicted = max(0.0, (slope * future_x + intercept) * seasonal_factor[future_date.dayofweek])
        rows.append(
            {
                "date": future_date,
                "predicted": predicted,
                "lower": max(0.0, predicted - 1.64 * residual_std),
                "upper": predicted + 1.64 * residual_std,
            }
        )
    return pd.DataFrame(rows), "naive_seasonal"


def forecast_for_service(account, service: str, horizon_days: int = None) -> int:
    horizon_days = horizon_days or settings.FORECAST_HORIZON_DAYS
    qs = CostRecord.objects.filter(account=account, service=service).order_by("date")
    daily = daily_series_dataframe(qs)
    if len(daily) < MIN_DATA_POINTS:
        return 0

    try:
        result, model_used = _forecast_with_prophet(daily, horizon_days)
    except Exception:
        logger.warning(
            "Prophet forecasting unavailable/failed for %s / %s, falling back to naive seasonal model",
            account, service, exc_info=True,
        )
        result, model_used = _forecast_naive_seasonal(daily, horizon_days)

    created = 0
    for _, row in result.iterrows():
        Forecast.objects.update_or_create(
            account=account,
            service=service,
            date=row["date"].date() if hasattr(row["date"], "date") else row["date"],
            defaults=dict(
                predicted_amount=round(float(row["predicted"]), 4),
                lower_bound=round(float(row["lower"]), 4),
                upper_bound=round(float(row["upper"]), 4),
                model_used=model_used,
            ),
        )
        created += 1
    return created


def run_forecasting(account, horizon_days: int = None) -> int:
    services = (
        CostRecord.objects.filter(account=account)
        .order_by()
        .values_list("service", flat=True)
        .distinct()
    )
    total = 0
    for service in services:
        try:
            total += forecast_for_service(account, service, horizon_days)
        except Exception:
            logger.exception("Forecasting failed for %s / %s", account, service)
    return total
