import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, InternalServerError

from app.core.errors import ApplicationError
from app.providers.openai import (
    ComplexityBatch,
    OpenAIComplexityClassifier,
    OpenAITranscriptionProvider,
)
from app.providers import openai as openai_module
from app.schemas.lecture import ComplexityCategory, ComplexityResult, TranscriptSegment
from app.schemas.media import AudioChunk


def transcript_segment(start: float = 0, end: float = 30) -> TranscriptSegment:
    return TranscriptSegment(start_seconds=start, end_seconds=end, text="A connected idea.")


def complexity_result(start: float = 0, end: float = 30) -> ComplexityResult:
    return ComplexityResult(
        start_seconds=start,
        end_seconds=end,
        complexity_score=4,
        category=ComplexityCategory.DENSE_CONCEPT,
        reason="Several ideas depend on one another.",
        confidence=0.9,
    )


def status_error(error_type: type[BadRequestError] | type[InternalServerError], status: int):
    request = httpx.Request("POST", "https://api.openai.test/v1")
    response = httpx.Response(status, request=request)
    return error_type("provider error", response=response, body=None)


def test_transcription_provider_maps_openai_text_to_timestamped_sections(
    tmp_path: Path,
) -> None:
    media_path = tmp_path / "lecture.mp4"
    media_path.write_bytes(b"video")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="First concept. Second concept. Third concept."
    )
    provider = OpenAITranscriptionProvider("test-key", "gpt-4o-transcribe", client)

    result = provider.transcribe(
        [AudioChunk(path=media_path, start_offset_seconds=0, duration_seconds=90)]
    )

    assert [segment.text for segment in result] == [
        "First concept.",
        "Second concept.",
        "Third concept.",
    ]
    assert [(segment.start_seconds, segment.end_seconds) for segment in result] == [
        (0, 30),
        (30, 60),
        (60, 90),
    ]
    call = client.audio.transcriptions.create.call_args.kwargs
    assert call["model"] == "gpt-4o-transcribe"
    assert call["response_format"] == "json"


def test_transcription_provider_uses_openai_segment_timestamps_for_whisper(
    tmp_path: Path,
) -> None:
    media_path = tmp_path / "lecture.mp4"
    media_path.write_bytes(b"video")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        segments=[SimpleNamespace(start=0, end=18.5, text="Timestamped section.")]
    )
    provider = OpenAITranscriptionProvider("test-key", "whisper-1", client)

    result = provider.transcribe(
        [AudioChunk(path=media_path, start_offset_seconds=0, duration_seconds=20)]
    )

    assert result == [
        TranscriptSegment(start_seconds=0, end_seconds=18.5, text="Timestamped section.")
    ]
    call = client.audio.transcriptions.create.call_args.kwargs
    assert call["response_format"] == "verbose_json"
    assert call["timestamp_granularities"] == ["segment"]


def test_transcription_provider_merges_chunks_with_absolute_timestamps(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.m4a"
    second_path = tmp_path / "second.m4a"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = [
        SimpleNamespace(text="First idea. Second idea."),
        SimpleNamespace(text="Final idea."),
    ]
    provider = OpenAITranscriptionProvider("test-key", "gpt-4o-transcribe", client)

    result = provider.transcribe(
        [
            AudioChunk(path=first_path, start_offset_seconds=0, duration_seconds=1200),
            AudioChunk(path=second_path, start_offset_seconds=1200, duration_seconds=300),
        ]
    )

    assert [(segment.start_seconds, segment.end_seconds, segment.text) for segment in result] == [
        (0, 600, "First idea."),
        (600, 1200, "Second idea."),
        (1200, 1500, "Final idea."),
    ]
    assert client.audio.transcriptions.create.call_count == 2


def test_transcription_retries_transient_connection_error_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    media_path = tmp_path / "lecture.m4a"
    media_path.write_bytes(b"audio")
    request = httpx.Request("POST", "https://api.openai.test/v1/audio/transcriptions")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = [
        APIConnectionError(request=request),
        SimpleNamespace(text="Recovered transcript."),
    ]
    monkeypatch.setattr(openai_module.time, "sleep", lambda _: None)
    caplog.set_level(logging.WARNING, logger="app.providers.openai")
    provider = OpenAITranscriptionProvider("test-key", "gpt-4o-transcribe", client)

    result = provider.transcribe(
        [AudioChunk(path=media_path, start_offset_seconds=0, duration_seconds=30)]
    )

    assert result == [
        TranscriptSegment(start_seconds=0, end_seconds=30, text="Recovered transcript.")
    ]
    assert client.audio.transcriptions.create.call_count == 2
    retry = next(record for record in caplog.records if record.message.endswith("retrying"))
    assert retry.provider == "openai:transcription"
    assert retry.attempt == 2
    assert retry.error_code == "APIConnectionError"


def test_transcription_does_not_retry_permanent_bad_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "lecture.m4a"
    media_path.write_bytes(b"audio")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = status_error(BadRequestError, 400)
    sleep = MagicMock()
    monkeypatch.setattr(openai_module.time, "sleep", sleep)
    provider = OpenAITranscriptionProvider("test-key", "gpt-4o-transcribe", client)

    with pytest.raises(ApplicationError) as raised:
        provider.transcribe(
            [AudioChunk(path=media_path, start_offset_seconds=0, duration_seconds=1200)]
        )

    assert raised.value.code == "TRANSCRIPTION_FAILED"
    assert client.audio.transcriptions.create.call_count == 1
    sleep.assert_not_called()


def test_transcription_exhausts_transient_retries_then_raises_application_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "lecture.m4a"
    media_path.write_bytes(b"audio")
    request = httpx.Request("POST", "https://api.openai.test/v1/audio/transcriptions")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = [
        APIConnectionError(request=request),
        APIConnectionError(request=request),
        APIConnectionError(request=request),
    ]
    monkeypatch.setattr(openai_module.time, "sleep", lambda _: None)
    provider = OpenAITranscriptionProvider("test-key", "gpt-4o-transcribe", client)

    with pytest.raises(ApplicationError) as raised:
        provider.transcribe(
            [AudioChunk(path=media_path, start_offset_seconds=0, duration_seconds=30)]
        )

    assert raised.value.code == "TRANSCRIPTION_FAILED"
    assert client.audio.transcriptions.create.call_count == 3


def test_classifier_uses_structured_response_and_preserves_timestamps() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=ComplexityBatch(segments=[complexity_result()])
    )
    provider = OpenAIComplexityClassifier("test-key", "gpt-5.4-mini", client)

    result = provider.classify([transcript_segment()])

    assert result == [complexity_result()]
    call = client.responses.parse.call_args.kwargs
    assert call["model"] == "gpt-5.4-mini"
    assert call["text_format"] is ComplexityBatch


def test_classifier_retries_transient_server_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.responses.parse.side_effect = [
        status_error(InternalServerError, 500),
        SimpleNamespace(output_parsed=ComplexityBatch(segments=[complexity_result()])),
    ]
    monkeypatch.setattr(openai_module.time, "sleep", lambda _: None)
    provider = OpenAIComplexityClassifier("test-key", "gpt-5.4-mini", client)

    result = provider.classify([transcript_segment()])

    assert result == [complexity_result()]
    assert client.responses.parse.call_count == 2


def test_classifier_rejects_changed_timestamps() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=ComplexityBatch(segments=[complexity_result(end=29)])
    )
    provider = OpenAIComplexityClassifier("test-key", "gpt-5.4-mini", client)

    with pytest.raises(ApplicationError) as raised:
        provider.classify([transcript_segment()])

    assert raised.value.code == "INVALID_PROVIDER_RESPONSE"
