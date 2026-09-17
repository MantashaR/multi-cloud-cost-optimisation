from datetime import date, timedelta

from django.db.models import Case, Count, F, IntegerField, Min, Sum, When
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AnalysisRun, Anomaly, CloudAccount, CostRecord, Forecast, Recommendation
from .pipeline import run_full_pipeline
from .serializers import (
    AnalysisRunSerializer,
    AnomalySerializer,
    CloudAccountSerializer,
    CostRecordSerializer,
    ForecastSerializer,
    RecommendationDetailSerializer,
    RecommendationSerializer,
)
from .tasks import run_full_pipeline_task


class CloudAccountViewSet(viewsets.ModelViewSet):
    queryset = CloudAccount.objects.all()
    serializer_class = CloudAccountSerializer


class CostRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = CostRecord.objects.select_related("account").all()
    serializer_class = CostRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if account := params.get("account"):
            qs = qs.filter(account_id=account)
        if provider := params.get("provider"):
            qs = qs.filter(account__provider=provider)
        if service := params.get("service"):
            qs = qs.filter(service=service)
        if start := params.get("start"):
            qs = qs.filter(date__gte=start)
        if end := params.get("end"):
            qs = qs.filter(date__lte=end)
        return qs


class AnomalyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Anomaly.objects.select_related("account").all()
    serializer_class = AnomalySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if account := params.get("account"):
            qs = qs.filter(account_id=account)
        if severity := params.get("severity"):
            qs = qs.filter(severity=severity)
        return qs


class ForecastViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Forecast.objects.select_related("account").all()
    serializer_class = ForecastSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if account := params.get("account"):
            qs = qs.filter(account_id=account)
        if service := params.get("service"):
            qs = qs.filter(service=service)
        return qs


class RecommendationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Recommendation.objects.select_related("account").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RecommendationDetailSerializer
        return RecommendationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if account := params.get("account"):
            qs = qs.filter(account_id=account)
        if status_ := params.get("status"):
            qs = qs.filter(status=status_)
        return qs

    @action(detail=True, methods=["patch"])
    def status_update(self, request, pk=None):
        rec = self.get_object()
        new_status = request.data.get("status")
        if new_status not in Recommendation.Status.values:
            return Response({"detail": "invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        rec.status = new_status
        rec.save(update_fields=["status", "updated_at"])
        return Response(RecommendationSerializer(rec).data)

    @action(detail=True, methods=["get"])
    def terraform(self, request, pk=None):
        rec = self.get_object()
        response = HttpResponse(rec.terraform_script, content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{rec.account.provider}_{rec.resource_id}.tf"'
        return response


class AnalysisRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AnalysisRun.objects.all()
    serializer_class = AnalysisRunSerializer

    @action(detail=False, methods=["post"])
    def trigger(self, request):
        run = AnalysisRun.objects.create()
        try:
            run_full_pipeline_task.delay(run.pk)
        except Exception:
            # No Celery worker/broker reachable (e.g. running the API alone) --
            # fall back to running the pipeline synchronously so the demo
            # still works.
            run_full_pipeline(run_id=run.pk)
        run.refresh_from_db()
        return Response(AnalysisRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["get"])
    def latest(self, request):
        run = AnalysisRun.objects.first()
        if not run:
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        return Response(AnalysisRunSerializer(run).data)


def _dashboard_view(request):
    from rest_framework.renderers import JSONRenderer

    today = date.today()
    trend_start = today - timedelta(days=60)

    spend_by_provider = list(
        CostRecord.objects.filter(date__gte=today - timedelta(days=30))
        .values("account__provider")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    spend_by_provider = [
        {"provider": row["account__provider"], "total": float(row["total"] or 0)}
        for row in spend_by_provider
    ]
    total_spend_30d = sum(row["total"] for row in spend_by_provider)

    daily_trend_qs = (
        CostRecord.objects.filter(date__gte=trend_start)
        .values("date", "account__provider")
        .annotate(total=Sum("amount"))
        .order_by("date")
    )
    trend_by_date = {}
    for row in daily_trend_qs:
        d = row["date"].isoformat()
        entry = trend_by_date.setdefault(d, {"date": d})
        entry[row["account__provider"]] = float(row["total"] or 0)
    daily_trend = list(trend_by_date.values())

    anomalies = AnomalySerializer(
        Anomaly.objects.select_related("account").order_by("-date", "-deviation_pct")[:20],
        many=True,
    ).data

    # Monthly cost-spike summary: turns the day-by-day anomaly list into the
    # question a FinOps stakeholder actually asks -- "which service drove the
    # overspend this month, and by how much" -- by rolling every anomaly's
    # excess-over-baseline up by (month, provider, service).
    severity_rank = Case(
        When(severity=Anomaly.Severity.CRITICAL, then=0),
        When(severity=Anomaly.Severity.HIGH, then=1),
        When(severity=Anomaly.Severity.MEDIUM, then=2),
        default=3,
        output_field=IntegerField(),
    )
    monthly_rows = (
        Anomaly.objects.annotate(month=TruncMonth("date"), severity_rank=severity_rank)
        .values("month", "account__provider", "service")
        .annotate(
            spike_count=Count("id"),
            total_excess=Sum(F("actual_amount") - F("expected_amount")),
            worst_severity_rank=Min("severity_rank"),
        )
        .order_by("-month", "-total_excess")
    )
    severity_labels = {0: "critical", 1: "high", 2: "medium", 3: "low"}
    monthly_cost_spikes = [
        {
            "month": row["month"].strftime("%Y-%m"),
            "provider": row["account__provider"],
            "service": row["service"],
            "spike_count": row["spike_count"],
            "total_excess_amount": float(row["total_excess"] or 0),
            "worst_severity": severity_labels[row["worst_severity_rank"]],
        }
        for row in monthly_rows
    ]

    priority_rank = Case(
        When(priority=Recommendation.Priority.HIGH, then=0),
        When(priority=Recommendation.Priority.MEDIUM, then=1),
        default=2,
        output_field=IntegerField(),
    )
    recommendations = RecommendationSerializer(
        Recommendation.objects.select_related("account")
        .filter(status=Recommendation.Status.PENDING)
        .annotate(priority_rank=priority_rank)
        .order_by("priority_rank", "-estimated_monthly_savings")[:20],
        many=True,
    ).data

    pending_savings_totals = Recommendation.objects.filter(
        status=Recommendation.Status.PENDING
    ).aggregate(
        monthly=Sum("estimated_monthly_savings"),
        annual=Sum("estimated_annual_savings"),
    )
    total_potential_savings = float(pending_savings_totals["monthly"] or 0)
    total_potential_annual_savings = float(pending_savings_totals["annual"] or 0)

    forecast_rows = (
        Forecast.objects.filter(date__gte=today)
        .values("date")
        .annotate(
            predicted=Sum("predicted_amount"),
            lower=Sum("lower_bound"),
            upper=Sum("upper_bound"),
        )
        .order_by("date")
    )
    forecast_series = [
        {
            "date": row["date"].isoformat(),
            "predicted": float(row["predicted"] or 0),
            "lower": float(row["lower"] or 0),
            "upper": float(row["upper"] or 0),
        }
        for row in forecast_rows
    ]

    last_run = AnalysisRun.objects.first()

    payload = {
        "total_spend_30d": total_spend_30d,
        "total_potential_monthly_savings": total_potential_savings,
        "total_potential_annual_savings": total_potential_annual_savings,
        "spend_by_provider": spend_by_provider,
        "daily_trend": daily_trend,
        "forecast_series": forecast_series,
        "anomalies": anomalies,
        "monthly_cost_spikes": monthly_cost_spikes,
        "recommendations": recommendations,
        "last_analysis_run": AnalysisRunSerializer(last_run).data if last_run else None,
        "account_count": CloudAccount.objects.filter(is_active=True).count(),
    }

    return HttpResponse(
        JSONRenderer().render(payload),
        content_type="application/json",
    )
