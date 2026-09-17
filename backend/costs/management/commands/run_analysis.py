from django.core.management.base import BaseCommand

from costs.pipeline import run_full_pipeline


class Command(BaseCommand):
    help = "Run the full pipeline: ingest costs, detect anomalies, forecast, generate right-sizing recommendations."

    def handle(self, *args, **options):
        run = run_full_pipeline()
        self.stdout.write(self.style.SUCCESS(
            f"AnalysisRun #{run.pk} [{run.status}] "
            f"records={run.records_ingested} anomalies={run.anomalies_found} "
            f"forecasts={run.forecasts_generated} recommendations={run.recommendations_generated}"
        ))
        if run.error_message:
            self.stdout.write(self.style.ERROR(run.error_message))
