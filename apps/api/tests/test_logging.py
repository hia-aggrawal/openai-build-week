import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_renders_structured_extra_fields() -> None:
    record = logging.LogRecord(
        name="studyflow.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="processing complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.provider = "transcription:openai,classification:openai"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "processing complete"
    assert payload["request_id"] == "request-123"
    assert payload["provider"] == "transcription:openai,classification:openai"
