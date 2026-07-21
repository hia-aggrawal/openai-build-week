from typing import Protocol

from app.schemas.lecture import ComplexityResult, TranscriptSegment
from app.schemas.media import AudioChunk


class TranscriptionProvider(Protocol):
    provider_name: str

    def transcribe(self, audio_chunks: list[AudioChunk]) -> list[TranscriptSegment]: ...


class ComplexityClassifier(Protocol):
    provider_name: str

    def classify(self, segments: list[TranscriptSegment]) -> list[ComplexityResult]: ...


class JobDispatcher(Protocol):
    def dispatch(self, job_id: str, request_id: str | None = None) -> None: ...
