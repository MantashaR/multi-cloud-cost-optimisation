from datetime import date, timedelta
from typing import List

from django.conf import settings

from .base import CostConnector, CostRecordDTO


class AWSCostConnector(CostConnector):
    """Real AWS Cost Explorer connector.

    Requires AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (or an attached IAM
    role) with `ce:GetCostAndUsage` permission. Only used when
    `USE_MOCK_CLOUD_DATA=false`; see costs/connectors/mock.py for the
    synthetic-data path used by default.
    """

    provider = "aws"

    def fetch_costs(self, start: date, end: date) -> List[CostRecordDTO]:
        import boto3

        client = boto3.client(
            "ce",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )

        # Cost Explorer's end date is exclusive.
        response = client.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": (end + timedelta(days=1)).isoformat(),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost", "UsageQuantity"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        )

        records: List[CostRecordDTO] = []
        for result in response.get("ResultsByTime", []):
            record_date = date.fromisoformat(result["TimePeriod"]["Start"])
            for group in result.get("Groups", []):
                service, region = group["Keys"]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                usage = float(group["Metrics"]["UsageQuantity"]["Amount"])
                records.append(
                    CostRecordDTO(
                        date=record_date,
                        service=service,
                        region=region or "global",
                        resource_id=f"aws-{service}-{region}",
                        amount=amount,
                        usage_quantity=usage,
                    )
                )
        return records
