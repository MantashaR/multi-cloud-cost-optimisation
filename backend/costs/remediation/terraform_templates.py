"""Renders Terraform HCL remediation scripts from a Recommendation. No
templating engine dependency -- these are simple enough for plain f-strings,
and keeping them readable here matters more than DRY-ing across providers.
"""

HEADER = """# Right-sizing remediation
# Account : {account_name} ({provider})
# Resource: {resource_id}
# Reason  : {rationale}
# Estimated monthly savings: ${savings:.2f} ({savings_pct:.0f}%)
"""


def _aws_downsize(rec) -> str:
    return HEADER.format(
        account_name=rec.account.name, provider="aws", resource_id=rec.resource_id,
        rationale=rec.rationale, savings=rec.estimated_monthly_savings, savings_pct=rec.estimated_savings_pct,
    ) + f"""
resource "aws_instance" "{_safe_name(rec.resource_id)}" {{
  # NOTE: import the existing instance before applying:
  #   terraform import aws_instance.{_safe_name(rec.resource_id)} <instance-id>
  instance_type = "{rec.recommended_instance_type}" # was "{rec.current_instance_type}"
  availability_zone = "{rec.region}a"

  tags = {{
    Name        = "{rec.resource_id}"
    RightSized  = "true"
    PreviousType = "{rec.current_instance_type}"
  }}
}}
"""


def _azure_downsize(rec) -> str:
    return HEADER.format(
        account_name=rec.account.name, provider="azure", resource_id=rec.resource_id,
        rationale=rec.rationale, savings=rec.estimated_monthly_savings, savings_pct=rec.estimated_savings_pct,
    ) + f"""
resource "azurerm_linux_virtual_machine" "{_safe_name(rec.resource_id)}" {{
  # NOTE: import the existing VM before applying:
  #   terraform import azurerm_linux_virtual_machine.{_safe_name(rec.resource_id)} <resource-id>
  name                = "{rec.resource_id}"
  location            = "{rec.region}"
  size                = "{rec.recommended_instance_type}" # was "{rec.current_instance_type}"

  tags = {{
    RightSized   = "true"
    PreviousSize = "{rec.current_instance_type}"
  }}
}}
"""


def _gcp_downsize(rec) -> str:
    return HEADER.format(
        account_name=rec.account.name, provider="gcp", resource_id=rec.resource_id,
        rationale=rec.rationale, savings=rec.estimated_monthly_savings, savings_pct=rec.estimated_savings_pct,
    ) + f"""
resource "google_compute_instance" "{_safe_name(rec.resource_id)}" {{
  # NOTE: import the existing instance before applying:
  #   terraform import google_compute_instance.{_safe_name(rec.resource_id)} <project>/<zone>/<instance-name>
  name         = "{rec.resource_id}"
  machine_type = "{rec.recommended_instance_type}" # was "{rec.current_instance_type}"
  zone         = "{rec.region}-a"

  labels = {{
    right_sized   = "true"
    previous_type = "{rec.current_instance_type.replace('-', '_')}"
  }}
}}
"""


_TERMINATE_TEMPLATE = """
# Idle resource -- utilisation over the trailing window was only
# {utilization:.1f}%, well below the {threshold:.0f}% right-sizing threshold.
# Recommended action: decommission after confirming with the resource owner.
#
# terraform destroy -target={resource_address}
"""


def _terminate(rec, resource_address: str) -> str:
    return HEADER.format(
        account_name=rec.account.name, provider=rec.account.provider, resource_id=rec.resource_id,
        rationale=rec.rationale, savings=rec.estimated_monthly_savings, savings_pct=rec.estimated_savings_pct,
    ) + _TERMINATE_TEMPLATE.format(
        utilization=rec.avg_utilization_pct or 0.0,
        threshold=100.0,
        resource_address=resource_address,
    )


def _safe_name(resource_id: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in resource_id).strip("_")


def render_terraform(rec) -> str:
    resource_type_by_provider = {
        "aws": "aws_instance",
        "azure": "azurerm_linux_virtual_machine",
        "gcp": "google_compute_instance",
    }

    if rec.action == rec.Action.TERMINATE:
        address = f"{resource_type_by_provider.get(rec.account.provider, 'resource')}.{_safe_name(rec.resource_id)}"
        return _terminate(rec, address)

    renderer = {
        "aws": _aws_downsize,
        "azure": _azure_downsize,
        "gcp": _gcp_downsize,
    }[rec.account.provider]
    return renderer(rec)
