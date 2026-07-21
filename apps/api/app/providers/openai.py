import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.errors import ApplicationError
from app.schemas.lecture import ComplexityResult, TranscriptSegment
from app.schemas.media import AudioChunk

logger = logging.getLogger(__name__)
OPENAI_MAX_ATTEMPTS = 3
OPENAI_RETRY_BASE_SECONDS = 0.25
ResultT = TypeVar("ResultT")


def _is_transient_openai_error(error: OpenAIError) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or error.status_code >= 500
    return False


def _call_openai_with_retry(call: Callable[[], ResultT], operation: str) -> ResultT:
    for attempt in range(1, OPENAI_MAX_ATTEMPTS + 1):
        try:
            return call()
        except OpenAIError as error:
            if not _is_transient_openai_error(error) or attempt == OPENAI_MAX_ATTEMPTS:
                raise
            delay_seconds = OPENAI_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "openai provider request retrying",
                extra={
                    "provider": f"openai:{operation}",
                    "attempt": attempt + 1,
                    "max_attempts": OPENAI_MAX_ATTEMPTS,
                    "retry_delay_ms": int(delay_seconds * 1000),
                    "error_code": type(error).__name__,
                },
            )
            time.sleep(delay_seconds)
    raise RuntimeError("OpenAI retry loop ended unexpectedly.")


class ComplexityBatch(BaseModel):
    segments: list[ComplexityResult]


class OpenAITranscriptionProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key, max_retries=0)

    def transcribe(self, audio_chunks: list[AudioChunk]) -> list[TranscriptSegment]:
        if not audio_chunks:
            raise ApplicationError("TRANSCRIPTION_FAILED", "No lecture audio was provided.")
        transcript: list[TranscriptSegment] = []
        for chunk in audio_chunks:
            transcript.extend(self._transcribe_chunk(chunk))
        return sorted(transcript, key=lambda segment: segment.start_seconds)

    def _transcribe_chunk(self, chunk: AudioChunk) -> list[TranscriptSegment]:
        try:
            with chunk.path.open("rb") as media:

                def request_transcription() -> Any:
                    media.seek(0)
                    if self.model == "whisper-1":
                        return self.client.audio.transcriptions.create(
                            model=self.model,
                            file=media,
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                        )
                    return self.client.audio.transcriptions.create(
                        model=self.model,
                        file=media,
                        response_format="json",
                    )

                response = _call_openai_with_retry(request_transcription, "transcription")
        except OpenAIError as error:
            raise ApplicationError(
                "TRANSCRIPTION_FAILED", "The lecture could not be transcribed."
            ) from error

        timestamped = self._timestamped_segments(response, chunk.duration_seconds)
        if timestamped:
            return self._offset_segments(timestamped, chunk.start_offset_seconds)
        text = self._value(response, "text")
        if not isinstance(text, str) or not text.strip():
            raise ApplicationError(
                "INVALID_PROVIDER_RESPONSE", "The transcription provider returned no text."
            )
        divided = self._divide_text(text, chunk.duration_seconds)
        return self._offset_segments(divided, chunk.start_offset_seconds)

    @staticmethod
    def _offset_segments(
        segments: list[TranscriptSegment], offset_seconds: float
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                start_seconds=round(segment.start_seconds + offset_seconds, 3),
                end_seconds=round(segment.end_seconds + offset_seconds, 3),
                text=segment.text,
            )
            for segment in segments
        ]

    @classmethod
    def _timestamped_segments(
        cls, response: Any, duration_seconds: float
    ) -> list[TranscriptSegment]:
        raw_segments = cls._value(response, "segments")
        if not raw_segments:
            return []
        try:
            segments = [
                TranscriptSegment(
                    start_seconds=float(cls._value(item, "start")),
                    end_seconds=min(float(cls._value(item, "end")), duration_seconds),
                    text=str(cls._value(item, "text")).strip(),
                )
                for item in raw_segments
            ]
        except (TypeError, ValueError, ValidationError) as error:
            raise ApplicationError(
                "INVALID_PROVIDER_RESPONSE",
                "The transcription provider returned invalid timestamps.",
            ) from error
        return segments

    @staticmethod
    def _value(value: Any, key: str) -> Any:
        return value.get(key) if isinstance(value, dict) else getattr(value, key, None)

    @staticmethod
    def _divide_text(text: str, duration_seconds: float) -> list[TranscriptSegment]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        section_count = min(len(sentences), max(1, round(duration_seconds / 30)))
        section_width = duration_seconds / section_count
        segments: list[TranscriptSegment] = []
        for index in range(section_count):
            first = index * len(sentences) // section_count
            last = (index + 1) * len(sentences) // section_count
            segments.append(
                TranscriptSegment(
                    start_seconds=round(index * section_width, 3),
                    end_seconds=round(
                        duration_seconds
                        if index == section_count - 1
                        else (index + 1) * section_width,
                        3,
                    ),
                    text=" ".join(sentences[first:last]),
                )
            )
        return segments


class OpenAIComplexityClassifier:
    provider_name = "openai"

    system_prompt = """You classify the cognitive complexity of timestamped lecture segments.
Return exactly one result for each input segment, in the same order, preserving its timestamps.
The score determines whether a learner may safely hear the segment faster, so account for both
reasoning difficulty and learning importance. Use score 1 only for filler, logistics, repetition,
or familiar review that can safely be accelerated. Definitions, formulas, procedures, key examples,
conclusions, emphasized points, and likely assessed material must receive at least score 3 even when
they are stated simply. Use score 5 for dense, multi-step concepts.
Choose the closest category and give a short learner-facing reason. Confidence measures how certain
you are about the classification. Do not choose playback speeds; the application owns that policy."""

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key, max_retries=0)

    def classify(self, segments: list[TranscriptSegment]) -> list[ComplexityResult]:
        payload = [segment.model_dump(mode="json") for segment in segments]
        try:
            response = _call_openai_with_retry(
                lambda: self.client.responses.parse(
                    model=self.model,
                    input=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    text_format=ComplexityBatch,
                ),
                "classification",
            )
        except OpenAIError as error:
            raise ApplicationError(
                "CLASSIFICATION_FAILED", "Lecture complexity could not be classified."
            ) from error
        parsed = response.output_parsed
        if parsed is None:
            raise ApplicationError(
                "INVALID_PROVIDER_RESPONSE", "The classification provider returned no result."
            )
        results = parsed.segments
        if len(results) != len(segments):
            raise ApplicationError(
                "INVALID_PROVIDER_RESPONSE",
                "The classification provider returned the wrong number of segments.",
            )
        for source, result in zip(segments, results, strict=True):
            if (
                result.start_seconds != source.start_seconds
                or result.end_seconds != source.end_seconds
            ):
                raise ApplicationError(
                    "INVALID_PROVIDER_RESPONSE",
                    "The classification provider changed transcript timestamps.",
                )
        return results
