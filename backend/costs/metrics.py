"""Prometheus metrics for the platform.

Request, latency and database metrics come from django-prometheus. The
FinOps numbers below are read from the database on every scrape, so they
always match what the dashboard shows and stay consistent across gunicorn
workers.
"""
import os
from datetime import timedelta

from django.db import DatabaseError
from django.db.models import Count, Max, Sum
from django.http import HttpResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily

from .models import AnalysisRun, Anomaly, CloudAccount, CostRecord, Recommendation

SPEND_WINDOW_DAYS = 30


class FinOpsCollector:
    def collect(self):
        try:
            yield from self._collect()
        except DatabaseError:
            # Tables don't exist yet (before the first migrate) -- export nothing.
            return

    def _collect(self):
        records = GaugeMetricFamily("cloudcost_cost_records", "Billing records stored")
        records.add_metric([], CostRecord.objects.count())
        yield records

        # Window is anchored on the newest billing date we have, not today,
        # so the numbers don't drop to zero between ingestion runs.
        spend = GaugeMetricFamily(
            "cloudcost_spend_usd",
            f"Cloud spend over the last {SPEND_WINDOW_DAYS} days of billing data",
            labels=["provider"],
        )
        latest = CostRecord.objects.aggregate(latest=Max("date"))["latest"]
        totals = {p: 0.0 for p in CloudAccount.Provider.values}
        if latest:
            rows = (
                CostRecord.objects.filter(date__gt=latest - timedelta(days=SPEND_WINDOW_DAYS))
                .values("account__provider")
                .annotate(total=Sum("amount"))
            )
            for row in rows:
                totals[row["account__provider"]] = float(row["total"] or 0)
        for provider, total in totals.items():
            spend.add_metric([provider], total)
        yield spend

        anomalies = GaugeMetricFamily(
            "cloudcost_anomalies", "Detected cost anomalies", labels=["severity"]
        )
        counts = dict(Anomaly.objects.values_list("severity").annotate(n=Count("id")))
        for severity in Anomaly.Severity.values:
            anomalies.add_metric([severity], counts.get(severity, 0))
        yield anomalies

        recs = GaugeMetricFamily(
            "cloudcost_recommendations", "Right-sizing recommendations", labels=["status"]
        )
        counts = dict(Recommendation.objects.values_list("status").annotate(n=Count("id")))
        for rec_status in Recommendation.Status.values:
            recs.add_metric([rec_status], counts.get(rec_status, 0))
        yield recs

        pending = Recommendation.objects.filter(status=Recommendation.Status.PENDING)
        savings = GaugeMetricFamily(
            "cloudcost_potential_monthly_savings_usd",
            "Projected monthly savings from pending recommendations",
        )
        savings.add_metric(
            [], float(pending.aggregate(s=Sum("estimated_monthly_savings"))["s"] or 0)
        )
        yield savings

        runs = GaugeMetricFamily(
            "cloudcost_analysis_runs", "Analysis pipeline runs", labels=["status"]
        )
        counts = dict(AnalysisRun.objects.values_list("status").annotate(n=Count("id")))
        for run_status in AnalysisRun.Status.values:
            runs.add_metric([run_status], counts.get(run_status, 0))
        yield runs

        finished = AnalysisRun.objects.filter(finished_at__isnull=False).first()
        if finished:
            ok = GaugeMetricFamily(
                "cloudcost_analysis_last_run_success",
                "1 if the most recent finished analysis run succeeded, else 0",
            )
            ok.add_metric([], 1 if finished.status == AnalysisRun.Status.SUCCESS else 0)
            yield ok

            duration = GaugeMetricFamily(
                "cloudcost_analysis_last_duration_seconds",
                "Duration of the most recent finished analysis run",
            )
            duration.add_metric([], (finished.finished_at - finished.started_at).total_seconds())
            yield duration

        last_success = AnalysisRun.objects.filter(status=AnalysisRun.Status.SUCCESS).first()
        if last_success and last_success.finished_at:
            ts = GaugeMetricFamily(
                "cloudcost_analysis_last_success_timestamp_seconds",
                "Unix time the last successful analysis run finished",
            )
            ts.add_metric([], last_success.finished_at.timestamp())
            yield ts


def metrics_view(request):
    finops = CollectorRegistry()
    finops.register(FinOpsCollector())

    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        # gunicorn runs several worker processes; merge their counters.
        app = CollectorRegistry()
        multiprocess.MultiProcessCollector(app)
    else:
        app = REGISTRY

    body = generate_latest(app) + generate_latest(finops)
    return HttpResponse(body, content_type=CONTENT_TYPE_LATEST)
