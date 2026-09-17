"""Static reference data shared by the mock connector and the right-sizing
engine: per-provider compute families ordered largest -> smallest with an
approximate relative daily on-demand cost. This keeps the synthetic cost
data and the "recommended smaller instance type" logic consistent, and gives
the Terraform generator something realistic to write into resource blocks.

Real relative pricing varies by region/OS/commitment; these are ballpark
US on-demand ratios good enough for a right-sizing demo, not a pricing API.
"""

AWS_EC2_FAMILY = [
    ("m5.4xlarge", 0.768),
    ("m5.2xlarge", 0.384),
    ("m5.xlarge", 0.192),
    ("m5.large", 0.096),
    ("c5.4xlarge", 0.680),
    ("c5.2xlarge", 0.340),
    ("c5.xlarge", 0.170),
    ("r5.2xlarge", 0.504),
    ("r5.xlarge", 0.252),
    ("r5.large", 0.126),
]

AZURE_VM_FAMILY = [
    ("Standard_D8s_v3", 0.768),
    ("Standard_D4s_v3", 0.384),
    ("Standard_D2s_v3", 0.192),
    ("Standard_E4s_v3", 0.504),
    ("Standard_E2s_v3", 0.252),
    ("Standard_F8s_v2", 0.678),
    ("Standard_F4s_v2", 0.339),
    ("Standard_B2s", 0.042),
]

GCP_COMPUTE_FAMILY = [
    ("n2-standard-8", 0.776),
    ("n2-standard-4", 0.388),
    ("n2-standard-2", 0.194),
    ("e2-standard-4", 0.268),
    ("e2-standard-2", 0.134),
    ("c2-standard-8", 0.836),
    ("c2-standard-4", 0.418),
]

# next_size_down() below just walks to the next tuple in a family list, so
# every family must be sorted most- to least-expensive *globally*, not just
# within its own sub-family (D/E/F, m5/c5/r5, n2/e2/c2, ...) -- otherwise
# "downsizing" from the cheap end of one sub-family can land on the
# expensive end of another and produce a negative "saving".
AWS_EC2_FAMILY.sort(key=lambda t: -t[1])
AZURE_VM_FAMILY.sort(key=lambda t: -t[1])
GCP_COMPUTE_FAMILY.sort(key=lambda t: -t[1])

FAMILY_BY_PROVIDER = {
    "aws": AWS_EC2_FAMILY,
    "azure": AZURE_VM_FAMILY,
    "gcp": GCP_COMPUTE_FAMILY,
}

COMPUTE_SERVICE_BY_PROVIDER = {
    "aws": "Amazon EC2",
    "azure": "Azure Virtual Machines",
    "gcp": "Compute Engine",
}

NON_COMPUTE_SERVICES_BY_PROVIDER = {
    "aws": ["Amazon S3", "Amazon RDS", "AWS Lambda", "Amazon CloudFront"],
    "azure": ["Azure Blob Storage", "Azure SQL Database", "Azure Functions", "Azure CDN"],
    "gcp": ["Cloud Storage", "Cloud SQL", "Cloud Functions", "Cloud CDN"],
}

REGIONS_BY_PROVIDER = {
    "aws": ["us-east-1", "eu-west-1", "ap-south-1"],
    "azure": ["eastus", "westeurope", "centralindia"],
    "gcp": ["us-central1", "europe-west1", "asia-south1"],
}


def next_size_down(provider: str, instance_type: str):
    """Return (smaller_type, relative_cost, current_relative_cost) or None
    if `instance_type` is already the smallest in its family."""
    family = FAMILY_BY_PROVIDER.get(provider, [])
    types = [t for t, _ in family]
    costs = dict(family)
    if instance_type not in types:
        return None
    idx = types.index(instance_type)
    if idx + 1 >= len(types):
        return None
    smaller_type = types[idx + 1]
    return smaller_type, costs[smaller_type], costs[instance_type]
