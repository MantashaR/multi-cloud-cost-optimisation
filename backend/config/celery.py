import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("cloudcost")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Re-run the full ingest -> anomaly-detection -> forecast -> right-sizing
# pipeline every 6 hours, simulating a continuously-refreshed FinOps feed.
# The dashboard also exposes a manual "Run Analysis" trigger for demos.
app.conf.beat_schedule = {
    "run-full-pipeline-every-6-hours": {
        "task": "costs.tasks.run_full_pipeline_task",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": (None,),
    },
}
