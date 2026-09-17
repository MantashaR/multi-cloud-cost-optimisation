import logging

from django.conf import settings
from sklearn.ensemble import IsolationForest

from costs.models import Anomaly, CostRecord

from .features import build_anomaly_features, daily_series_dataframe

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 14


def _severity_for(deviation_pct: float) -> str:
    if deviation_pct >= 200:
        return Anomaly.Severity.CRITICAL
    if deviation_pct >= 100:
        return Anomaly.Severity.HIGH
    if deviation_pct >= 50:
        return Anomaly.Severity.MEDIUM
    return Anomaly.Severity.LOW


def detect_anomalies_for_service(account, service: str, window_days: int = 90) -> int:
    """Run Isolation Forest over the trailing `window_days` of daily cost
    for one (account, service) pair and persist any flagged anomalies.
    Returns the number of anomalies found.
    """
    qs = (
        CostRecord.objects.filter(account=account, service=service)
        .order_by("date")
    )
    daily = daily_series_dataframe(qs)
    if len(daily) < MIN_DATA_POINTS:
        return 0

    daily = daily.tail(window_days).reset_index(drop=True)
    features = build_anomaly_features(daily)

    feature_cols = ["amount", "dayofweek", "rolling_mean_7", "rolling_std_7", "deviation", "pct_change"]
    X = features[feature_cols].values

    model = IsolationForest(
        n_estimators=200,
        contamination=settings.ANOMALY_CONTAMINATION,
        random_state=42,
    )
    model.fit(X)
    predictions = model.predict(X)  # -1 = anomaly, 1 = normal
    scores = model.decision_function(X)  # lower = more anomalous

    found = 0
    for i, row in features.iterrows():
        if predictions[i] != -1:
            continue
        expected = row["rolling_mean_7"] if row["rolling_mean_7"] > 0 else row["amount"]
        deviation_pct = 0.0 if expected == 0 else ((row["amount"] - expected) / expected) * 100
        if deviation_pct <= 0:
            # Isolation Forest can flag unusually *low* spend too; we only
            # surface cost overruns as "anomalies" for a FinOps audience.
            continue

        severity = _severity_for(deviation_pct)
        Anomaly.objects.update_or_create(
            account=account,
            service=service,
            date=row["date"].date(),
            defaults=dict(
                actual_amount=round(row["amount"], 4),
                expected_amount=round(expected, 4),
                deviation_pct=round(deviation_pct, 2),
                score=round(float(scores[i]), 4),
                severity=severity,
                method="isolation_forest",
                description=(
                    f"{service} spend on {row['date'].date()} was "
                    f"${row['amount']:.2f}, {deviation_pct:.0f}% above the "
                    f"trailing 7-day baseline of ${expected:.2f}."
                ),
            ),
        )
        found += 1

    return found


def run_anomaly_detection(account) -> int:
    services = (
        CostRecord.objects.filter(account=account)
        .order_by()
        .values_list("service", flat=True)
        .distinct()
    )
    total = 0
    for service in services:
        try:
            total += detect_anomalies_for_service(account, service)
        except Exception:
            logger.exception("Anomaly detection failed for %s / %s", account, service)
    return total
