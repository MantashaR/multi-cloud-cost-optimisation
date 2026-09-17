from django.db import models


class CloudAccount(models.Model):
    class Provider(models.TextChoices):
        AWS = "aws", "AWS"
        AZURE = "azure", "Azure"
        GCP = "gcp", "GCP"

    provider = models.CharField(max_length=10, choices=Provider.choices)
    name = models.CharField(max_length=120)
    external_id = models.CharField(
        max_length=120, help_text="Account ID / Subscription ID / Project ID"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider", "name"]
        unique_together = ("provider", "external_id")

    def __str__(self):
        return f"{self.get_provider_display()}: {self.name}"


class CostRecord(models.Model):
    account = models.ForeignKey(CloudAccount, on_delete=models.CASCADE, related_name="cost_records")
    date = models.DateField(db_index=True)
    service = models.CharField(max_length=120)
    region = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=120)
    instance_type = models.CharField(max_length=60, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    usage_quantity = models.FloatField(null=True, blank=True)
    avg_utilization_pct = models.FloatField(null=True, blank=True)
    workload_tag = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-date"]
        unique_together = ("account", "date", "service", "resource_id")
        indexes = [
            models.Index(fields=["account", "service", "date"]),
        ]

    def __str__(self):
        return f"{self.account} / {self.service} / {self.date} / ${self.amount}"


class Anomaly(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    account = models.ForeignKey(CloudAccount, on_delete=models.CASCADE, related_name="anomalies")
    service = models.CharField(max_length=120)
    date = models.DateField()
    actual_amount = models.DecimalField(max_digits=12, decimal_places=4)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=4)
    deviation_pct = models.FloatField()
    score = models.FloatField(help_text="Isolation Forest anomaly score (lower = more anomalous)")
    severity = models.CharField(max_length=10, choices=Severity.choices)
    method = models.CharField(max_length=40, default="isolation_forest")
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-deviation_pct"]
        unique_together = ("account", "service", "date")

    def __str__(self):
        return f"Anomaly[{self.severity}] {self.account} {self.service} {self.date}"


class Forecast(models.Model):
    account = models.ForeignKey(CloudAccount, on_delete=models.CASCADE, related_name="forecasts")
    service = models.CharField(max_length=120)
    date = models.DateField()
    predicted_amount = models.DecimalField(max_digits=12, decimal_places=4)
    lower_bound = models.DecimalField(max_digits=12, decimal_places=4)
    upper_bound = models.DecimalField(max_digits=12, decimal_places=4)
    model_used = models.CharField(max_length=30, default="prophet")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        unique_together = ("account", "service", "date")

    def __str__(self):
        return f"Forecast {self.account} {self.service} {self.date}"


class Recommendation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPLIED = "applied", "Applied"
        DISMISSED = "dismissed", "Dismissed"

    class Action(models.TextChoices):
        DOWNSIZE = "downsize", "Downsize"
        TERMINATE = "terminate", "Terminate idle resource"

    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    account = models.ForeignKey(CloudAccount, on_delete=models.CASCADE, related_name="recommendations")
    service = models.CharField(max_length=120)
    resource_id = models.CharField(max_length=120)
    region = models.CharField(max_length=60)
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.DOWNSIZE)
    current_instance_type = models.CharField(max_length=60, blank=True, default="")
    recommended_instance_type = models.CharField(max_length=60, blank=True, default="")
    avg_utilization_pct = models.FloatField(null=True, blank=True)
    current_monthly_cost = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_monthly_savings = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_annual_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estimated_savings_pct = models.FloatField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    projected_utilization_pct = models.FloatField(
        null=True, blank=True,
        help_text="Utilisation the resource would run at after applying this recommendation",
    )
    rationale = models.TextField(blank=True, default="")
    terraform_script = models.TextField(blank=True, default="")
    terraform_file_path = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Priority is a derived display label (see rightsizing.py); ordering
        # by savings amount is what actually matters for ranking impact.
        ordering = ["-estimated_monthly_savings"]
        unique_together = ("account", "resource_id")

    def __str__(self):
        return f"Recommendation {self.account} {self.resource_id} -> save ${self.estimated_monthly_savings}/mo"


class AnalysisRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_ingested = models.IntegerField(default=0)
    anomalies_found = models.IntegerField(default=0)
    forecasts_generated = models.IntegerField(default=0)
    recommendations_generated = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"AnalysisRun #{self.pk} [{self.status}]"
