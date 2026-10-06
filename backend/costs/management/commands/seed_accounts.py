from django.core.management.base import BaseCommand

from costs.models import CloudAccount

DEMO_ACCOUNTS = [
    ("aws", "Demo Co - AWS Prod", "123456789012"),
    ("azure", "Demo Co - Azure Prod", "b1f2a3c4-d5e6-4a7b-8c9d-0e1f2a3b4c5d"),
    ("gcp", "Demo Co - GCP Prod", "hcl-dbs-gcp-prod"),
]


class Command(BaseCommand):
    help = "Seed a handful of demo CloudAccount rows (one per provider)."

    def handle(self, *args, **options):
        for provider, name, external_id in DEMO_ACCOUNTS:
            account, created = CloudAccount.objects.get_or_create(
                provider=provider,
                external_id=external_id,
                defaults={"name": name},
            )
            verb = "Created" if created else "Already exists"
            self.stdout.write(self.style.SUCCESS(f"{verb}: {account}"))
