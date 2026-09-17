import hashlib
from datetime import date, timedelta
from typing import List

import numpy as np

from costs.catalog import (
    COMPUTE_SERVICE_BY_PROVIDER,
    FAMILY_BY_PROVIDER,
    NON_COMPUTE_SERVICES_BY_PROVIDER,
    REGIONS_BY_PROVIDER,
)

from .base import CostConnector, CostRecordDTO


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:8], 16)


class MockCostConnector(CostConnector):
    """Generates realistic, reproducible synthetic multi-cloud billing data
    so the whole platform (ingestion -> anomaly detection -> forecasting ->
    right-sizing -> Terraform generation) works end to end with zero cloud
    credentials.

    Data is deterministic per (account, resource, date): re-ingesting the
    same date range always produces the same numbers, and re-ingesting a new
    trailing window just extends the series, exactly like a real billing API.
    """

    provider = "mock"

    def fetch_costs(self, start: date, end: date) -> List[CostRecordDTO]:
        provider = self.account.provider
        records: List[CostRecordDTO] = []

        compute_service = COMPUTE_SERVICE_BY_PROVIDER[provider]
        family = FAMILY_BY_PROVIDER[provider]
        regions = REGIONS_BY_PROVIDER[provider]

        # 3 compute resources (VMs/instances) with varying utilisation profiles
        for i in range(3):
            resource_id = f"{provider}-{self.account.external_id}-compute-{i}"
            seed = _stable_seed(self.account.external_id, resource_id)
            rng = np.random.default_rng(seed)

            instance_type = family[rng.integers(0, min(4, len(family)))][0]
            region = regions[seed % len(regions)]
            underutilised = (seed % 100) < 40  # ~40% of instances are idle/over-provisioned
            base_utilization = rng.uniform(4, 22) if underutilised else rng.uniform(45, 88)
            base_daily_cost = dict(family)[instance_type] * 24  # relative $/hr * 24h

            records.extend(
                self._build_series(
                    start, end, resource_id, compute_service, region, seed,
                    base_daily_cost, instance_type=instance_type,
                    base_utilization=base_utilization,
                )
            )

        # Non-compute services (storage, managed DB, functions, CDN) - no instance_type
        for svc in NON_COMPUTE_SERVICES_BY_PROVIDER[provider]:
            resource_id = f"{provider}-{self.account.external_id}-{svc.lower().replace(' ', '-')}"
            seed = _stable_seed(self.account.external_id, resource_id)
            region = regions[seed % len(regions)]
            base_daily_cost = 8 + (seed % 40)
            records.extend(
                self._build_series(
                    start, end, resource_id, svc, region, seed, base_daily_cost,
                )
            )

        return records

    @staticmethod
    def _build_series(
        start, end, resource_id, service, region, seed, base_daily_cost,
        instance_type="", base_utilization=None,
    ) -> List[CostRecordDTO]:
        rng = np.random.default_rng(seed)
        days = (end - start).days + 1
        records = []

        # Slow upward trend + weekly seasonality (lower spend on weekends) + noise
        trend = np.linspace(1.0, rng.uniform(1.05, 1.25), days)
        weekday_factor = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.65, 0.6])
        noise = rng.normal(1.0, 0.06, days)

        # Deterministic anomaly spikes on ~4% of days
        spike_days = set(
            d for d in range(days) if _stable_seed(resource_id, str(d)) % 100 < 4
        )

        for d in range(days):
            current_date = start + timedelta(days=d)
            factor = trend[d] * weekday_factor[current_date.weekday()] * noise[d]
            if d in spike_days:
                factor *= rng.uniform(2.2, 4.5)

            amount = round(base_daily_cost * factor, 4)

            utilization = None
            if base_utilization is not None:
                utilization = float(np.clip(rng.normal(base_utilization, 4), 1, 98))

            records.append(
                CostRecordDTO(
                    date=current_date,
                    service=service,
                    region=region,
                    resource_id=resource_id,
                    amount=amount,
                    instance_type=instance_type,
                    usage_quantity=round(amount / max(base_daily_cost, 0.01), 3),
                    avg_utilization_pct=utilization,
                    workload_tag="production" if seed % 3 else "staging",
                )
            )
        return records
