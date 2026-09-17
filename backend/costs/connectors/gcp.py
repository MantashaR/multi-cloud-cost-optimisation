from datetime import date
from typing import List

from django.conf import settings

from .base import CostConnector, CostRecordDTO


class GCPCostConnector(CostConnector):
    """Real GCP Billing connector.

    GCP does not expose a query-by-date-range billing REST API the way AWS
    and Azure do -- the supported pattern is exporting billing data to
    BigQuery and querying it from there. This connector expects that export
    to already exist (see GCP_BILLING_ACCOUNT_ID / GCP_PROJECT_ID /
    GOOGLE_APPLICATION_CREDENTIALS) and runs a standard cost-by-service query
    against it. Only used when `USE_MOCK_CLOUD_DATA=false`.
    """

    provider = "gcp"

    def fetch_costs(self, start: date, end: date) -> List[CostRecordDTO]:
        from google.cloud import bigquery

        client = bigquery.Client(project=settings.GCP_PROJECT_ID)

        query = f"""
            SELECT
              DATE(usage_start_time) AS usage_date,
              service.description AS service,
              location.region AS region,
              SUM(cost) AS amount
            FROM `{settings.GCP_PROJECT_ID}.billing_export.gcp_billing_export_v1`
            WHERE DATE(usage_start_time) BETWEEN @start AND @end
            GROUP BY usage_date, service, region
            ORDER BY usage_date
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start", "DATE", start.isoformat()),
                bigquery.ScalarQueryParameter("end", "DATE", end.isoformat()),
            ]
        )

        records: List[CostRecordDTO] = []
        for row in client.query(query, job_config=job_config).result():
            region = row.region or "global"
            records.append(
                CostRecordDTO(
                    date=row.usage_date,
                    service=row.service,
                    region=region,
                    resource_id=f"gcp-{row.service}-{region}",
                    amount=float(row.amount),
                )
            )
        return records
