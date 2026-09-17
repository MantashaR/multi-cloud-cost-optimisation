from datetime import date
from typing import List

from django.conf import settings

from .base import CostConnector, CostRecordDTO


class AzureCostConnector(CostConnector):
    """Real Azure Cost Management connector.

    Requires an app registration (AZURE_TENANT_ID / AZURE_CLIENT_ID /
    AZURE_CLIENT_SECRET) with Cost Management Reader on the subscription.
    Only used when `USE_MOCK_CLOUD_DATA=false`.
    """

    provider = "azure"

    def fetch_costs(self, start: date, end: date) -> List[CostRecordDTO]:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.costmanagement import CostManagementClient

        credential = ClientSecretCredential(
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            client_secret=settings.AZURE_CLIENT_SECRET,
        )
        client = CostManagementClient(credential)

        scope = f"/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}"
        query_definition = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceLocation"},
                ],
            },
        }

        result = client.query.usage(scope, query_definition)

        records: List[CostRecordDTO] = []
        columns = [c.name for c in result.columns]
        for row in result.rows:
            row_dict = dict(zip(columns, row))
            record_date = date.fromisoformat(str(row_dict["UsageDate"]))
            service = row_dict.get("ServiceName", "Unknown")
            region = row_dict.get("ResourceLocation", "global")
            amount = float(row_dict.get("PreTaxCost", 0))
            records.append(
                CostRecordDTO(
                    date=record_date,
                    service=service,
                    region=region,
                    resource_id=f"azure-{service}-{region}",
                    amount=amount,
                )
            )
        return records
