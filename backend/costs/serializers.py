from rest_framework import serializers

from .models import AnalysisRun, Anomaly, CloudAccount, CostRecord, Forecast, Recommendation


class CloudAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudAccount
        fields = ["id", "provider", "name", "external_id", "is_active", "created_at"]


class CostRecordSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    provider = serializers.CharField(source="account.provider", read_only=True)

    class Meta:
        model = CostRecord
        fields = [
            "id", "account", "account_name", "provider", "date", "service", "region",
            "resource_id", "instance_type", "amount", "usage_quantity",
            "avg_utilization_pct", "workload_tag",
        ]


class AnomalySerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    provider = serializers.CharField(source="account.provider", read_only=True)

    class Meta:
        model = Anomaly
        fields = [
            "id", "account", "account_name", "provider", "service", "date",
            "actual_amount", "expected_amount", "deviation_pct", "score",
            "severity", "method", "description", "created_at",
        ]


class ForecastSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    provider = serializers.CharField(source="account.provider", read_only=True)

    class Meta:
        model = Forecast
        fields = [
            "id", "account", "account_name", "provider", "service", "date",
            "predicted_amount", "lower_bound", "upper_bound", "model_used",
        ]


class RecommendationSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    provider = serializers.CharField(source="account.provider", read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            "id", "account", "account_name", "provider", "service", "resource_id", "region",
            "action", "current_instance_type", "recommended_instance_type",
            "avg_utilization_pct", "current_monthly_cost", "estimated_monthly_savings",
            "estimated_savings_pct", "rationale", "terraform_file_path", "status",
            "created_at", "updated_at",
        ]


class RecommendationDetailSerializer(RecommendationSerializer):
    class Meta(RecommendationSerializer.Meta):
        fields = RecommendationSerializer.Meta.fields + ["terraform_script"]


class AnalysisRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisRun
        fields = [
            "id", "status", "started_at", "finished_at", "records_ingested",
            "anomalies_found", "forecasts_generated", "recommendations_generated",
            "error_message",
        ]
