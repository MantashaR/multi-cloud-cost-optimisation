from django.core.management.base import BaseCommand

from costs.models import CloudAccount
from costs.pipeline import ingest_costs_for_account


class Command(BaseCommand):
    help = "Ingest (mock or real, per USE_MOCK_CLOUD_DATA) billing data for all active cloud accounts."

    def add_arguments(self, parser):
        parser.add_argument("--days-back", type=int, default=180)

    def handle(self, *args, **options):
        days_back = options["days_back"]
        for account in CloudAccount.objects.filter(is_active=True):
            count = ingest_costs_for_account(account, days_back=days_back)
            self.stdout.write(self.style.SUCCESS(f"{account}: ingested {count} cost records"))
