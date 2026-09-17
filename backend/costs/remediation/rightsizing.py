import logging
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Sum

from costs.catalog import next_size_down
from costs.models import CostRecord, Recommendation

from .terraform_templates import render_terraform

logger = logging.getLogger(__name__)

IDLE_UTILIZATION_THRESHOLD = 8.0


def generate_recommendations(account, window_days: int = 30) -> int:
    """Look at every distinct compute resource for `account` over the
    trailing `window_days`, and for anything persistently under-utilised
    either recommend downsizing to the next smaller instance in its family
    (costs.catalog) or, if it's essentially idle, recommend termination.
    Persists a Recommendation plus a rendered Terraform remediation script
    for each finding.
    """
    resources = (
        CostRecord.objects.filter(account=account, avg_utilization_pct__isnull=False)
        .order_by()
        .values("resource_id", "service", "region", "instance_type")
        .distinct()
    )

    threshold = settings.RIGHTSIZING_UTILIZATION_THRESHOLD
    created = 0

    for resource in resources:
        qs = CostRecord.objects.filter(
            account=account, resource_id=resource["resource_id"]
        ).order_by("-date")[:window_days]

        agg = qs.aggregate(avg_util=Avg("avg_utilization_pct"), total_cost=Sum("amount"))
        avg_util = agg["avg_util"]
        total_cost = float(agg["total_cost"] or 0)
        if avg_util is None or avg_util >= threshold:
            continue

        current_monthly_cost = total_cost * (30 / max(qs.count(), 1))
        instance_type = resource["instance_type"]

        if avg_util < IDLE_UTILIZATION_THRESHOLD or not instance_type:
            action = Recommendation.Action.TERMINATE
            recommended_type = ""
            estimated_savings = current_monthly_cost * 0.95
            rationale = (
                f"Average utilisation over the last {window_days} days was only "
                f"{avg_util:.1f}%. This resource appears idle and is a candidate "
                f"for decommissioning rather than resizing."
            )
        else:
            downsize = next_size_down(account.provider, instance_type)
            if downsize is None:
                continue
            recommended_type, new_relative_cost, current_relative_cost = downsize
            action = Recommendation.Action.DOWNSIZE
            reduction_ratio = 1 - (new_relative_cost / current_relative_cost)
            estimated_savings = current_monthly_cost * reduction_ratio
            rationale = (
                f"Average utilisation over the last {window_days} days was only "
                f"{avg_util:.1f}%, well below the {threshold:.0f}% target. "
                f"{instance_type} is over-provisioned for this workload."
            )

        estimated_savings_pct = (
            (estimated_savings / current_monthly_cost) * 100 if current_monthly_cost else 0
        )

        rec, _ = Recommendation.objects.update_or_create(
            account=account,
            resource_id=resource["resource_id"],
            defaults=dict(
                service=resource["service"],
                region=resource["region"],
                action=action,
                current_instance_type=instance_type,
                recommended_instance_type=recommended_type,
                avg_utilization_pct=round(avg_util, 2),
                current_monthly_cost=round(current_monthly_cost, 2),
                estimated_monthly_savings=round(estimated_savings, 2),
                estimated_savings_pct=round(estimated_savings_pct, 2),
                rationale=rationale,
            ),
        )

        script = render_terraform(rec)
        rec.terraform_script = script

        out_dir = Path(settings.GENERATED_TERRAFORM_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"{rec.account.provider}_{rec.resource_id}.tf"
        file_path.write_text(script)
        rec.terraform_file_path = str(file_path.relative_to(settings.BASE_DIR))
        rec.save(update_fields=["terraform_script", "terraform_file_path"])

        created += 1

    return created
