from django.contrib import admin

from .models import AnalysisRun, Anomaly, CloudAccount, CostRecord, Forecast, Recommendation


@admin.register(CloudAccount)
class CloudAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "external_id", "is_active", "created_at")
    list_filter = ("provider", "is_active")


@admin.register(CostRecord)
class CostRecordAdmin(admin.ModelAdmin):
    list_display = ("account", "date", "service", "region", "resource_id", "amount", "avg_utilization_pct")
    list_filter = ("account", "service")
    date_hierarchy = "date"


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ("account", "service", "date", "actual_amount", "expected_amount", "deviation_pct", "severity")
    list_filter = ("account", "severity", "service")


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ("account", "service", "date", "predicted_amount", "lower_bound", "upper_bound", "model_used")
    list_filter = ("account", "service", "model_used")


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "account", "resource_id", "action", "current_instance_type",
        "recommended_instance_type", "estimated_monthly_savings", "status",
    )
    list_filter = ("account", "action", "status")


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "started_at", "finished_at", "records_ingested", "anomalies_found", "recommendations_generated")
