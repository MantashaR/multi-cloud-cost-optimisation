from django.conf import settings

from .base import CostConnector, CostRecordDTO
from .mock import MockCostConnector


def get_connector(account) -> CostConnector:
    """Factory: returns the connector to use for a given CloudAccount.

    Every connector implements the same `fetch_costs(start, end)` interface,
    so `USE_MOCK_CLOUD_DATA=false` (plus real credentials in the environment)
    is the only change needed to switch a deployment from synthetic data to
    live AWS/Azure/GCP billing APIs.
    """
    if settings.USE_MOCK_CLOUD_DATA:
        return MockCostConnector(account)

    if account.provider == "aws":
        from .aws import AWSCostConnector

        return AWSCostConnector(account)
    if account.provider == "azure":
        from .azure import AzureCostConnector

        return AzureCostConnector(account)
    if account.provider == "gcp":
        from .gcp import GCPCostConnector

        return GCPCostConnector(account)

    raise ValueError(f"Unsupported provider: {account.provider}")


__all__ = ["CostConnector", "CostRecordDTO", "get_connector"]
