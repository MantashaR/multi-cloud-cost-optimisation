import logging
from datetime import date, timedelta

from costs.connectors import get_connector
from costs.ml.anomaly import run_anomaly_detection
from costs.ml.forecast import run_forecasting
from costs.models import AnalysisRun, CloudAccount, CostRecord
from costs.remediation.rightsizing import generate_recommendations

logger = logging.getLogger(__name__)


def ingest_costs_for_account(account: CloudAccount, days_back: int = 180) -> int:
    connector = get_connector(account)
    end = date.today()
    start = end - timedelta(days=days_back)

    records = connector.fetch_costs(start, end)

    objs = [
        CostRecord(
            account=account,
            date=r.date,
            service=r.service,
            region=r.region,
            resource_id=r.resource_id,
            instance_type=r.instance_type or "",
            amount=r.amount,
            usage_quantity=r.usage_quantity,
            avg_utilization_pct=r.avg_utilization_pct,
            workload_tag=r.workload_tag,
        )
        for r in records
    ]

    CostRecord.objects.bulk_create(
        objs,
        update_conflicts=True,
        unique_fields=["account", "date", "service", "resource_id"],
        update_fields=["region", "instance_type", "amount", "usage_quantity", "avg_utilization_pct", "workload_tag"],
    )
    return len(objs)


def run_full_pipeline(run_id: int = None) -> AnalysisRun:
    run = AnalysisRun.objects.get(pk=run_id) if run_id else AnalysisRun.objects.create()
    try:
        records_ingested = 0
        anomalies_found = 0
        forecasts_generated = 0
        recommendations_generated = 0

        for account in CloudAccount.objects.filter(is_active=True):
            records_ingested += ingest_costs_for_account(account)
            anomalies_found += run_anomaly_detection(account)
            forecasts_generated += run_forecasting(account)
            recommendations_generated += generate_recommendations(account)

        run.records_ingested = records_ingested
        run.anomalies_found = anomalies_found
        run.forecasts_generated = forecasts_generated
        run.recommendations_generated = recommendations_generated
        run.status = AnalysisRun.Status.SUCCESS
    except Exception as exc:
        logger.exception("Analysis pipeline failed")
        run.status = AnalysisRun.Status.FAILED
        run.error_message = str(exc)
    finally:
        from django.utils import timezone

        run.finished_at = timezone.now()
        run.save()

    return run
