from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import logging

from celery import Celery

PROCESS_LECTURE_TASK = "studyflow.process_lecture"
logger = logging.getLogger(__name__)


class InProcessJobDispatcher:
    """In-process dispatcher for local mock and provider development."""

    def __init__(self, process: Callable[[str, str | None], None]) -> None:
        self.process = process
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studyflow-mock")

    def dispatch(self, job_id: str, request_id: str | None = None) -> None:
        try:
            future = self.executor.submit(self.process, job_id, request_id)
        except RuntimeError:
            logger.exception(
                "job dispatch failed",
                extra={"job_id": job_id, "request_id": request_id, "dispatcher": "in_process"},
            )
            raise

        def log_processing_failure(completed: object) -> None:
            error = future.exception()
            if error is not None:
                logger.error(
                    "dispatched job failed",
                    exc_info=(type(error), error, error.__traceback__),
                    extra={
                        "job_id": job_id,
                        "request_id": request_id,
                        "dispatcher": "in_process",
                    },
                )

        future.add_done_callback(log_processing_failure)


class CeleryJobDispatcher:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def dispatch(self, job_id: str, request_id: str | None = None) -> None:
        try:
            self.celery_app.send_task(PROCESS_LECTURE_TASK, args=[job_id, request_id])
        except Exception:
            logger.exception(
                "job dispatch failed",
                extra={"job_id": job_id, "request_id": request_id, "dispatcher": "celery"},
            )
            raise
