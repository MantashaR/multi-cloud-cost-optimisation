from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class CostRecordDTO:
    """Provider-agnostic shape every connector normalises its billing data
    into, before it is persisted as a `costs.models.CostRecord`."""

    date: date
    service: str
    region: str
    resource_id: str
    amount: float
    instance_type: Optional[str] = ""
    usage_quantity: Optional[float] = None
    avg_utilization_pct: Optional[float] = None
    workload_tag: str = ""


class CostConnector(ABC):
    """Common interface every cloud billing connector must implement.

    Keeping ingestion, anomaly detection, forecasting, and the API behind
    this single interface is what lets the platform be genuinely multi-cloud:
    none of that code cares whether the data came from the mock generator or
    a real AWS Cost Explorer / Azure Cost Management / GCP Billing export.
    """

    provider = "generic"

    def __init__(self, account):
        self.account = account

    @abstractmethod
    def fetch_costs(self, start: date, end: date) -> List[CostRecordDTO]:
        """Return normalised daily cost records for `account` between
        `start` and `end` (inclusive)."""
        raise NotImplementedError
