from celery import shared_task

from costs.pipeline import run_full_pipeline


@shared_task
def run_full_pipeline_task(run_id: int):
    run_full_pipeline(run_id=run_id)
