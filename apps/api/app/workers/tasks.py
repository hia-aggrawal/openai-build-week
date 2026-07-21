from app.api.dependencies import process_job
from app.workers.celery_app import celery_app
from app.workers.dispatcher import PROCESS_LECTURE_TASK


@celery_app.task(name=PROCESS_LECTURE_TASK)
def process_lecture(job_id: str, request_id: str | None = None) -> None:
    process_job(job_id, request_id)
