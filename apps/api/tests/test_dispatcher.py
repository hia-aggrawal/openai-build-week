from unittest.mock import MagicMock

from app.workers.dispatcher import CeleryJobDispatcher, PROCESS_LECTURE_TASK


def test_celery_dispatcher_enqueues_job_id() -> None:
    celery_app = MagicMock()

    CeleryJobDispatcher(celery_app).dispatch("job-123", request_id="request-123")

    celery_app.send_task.assert_called_once_with(
        PROCESS_LECTURE_TASK, args=["job-123", "request-123"]
    )
