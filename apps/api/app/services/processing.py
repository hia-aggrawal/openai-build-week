import logging
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.models.lecture import ProcessingStage
from app.providers.interfaces import ComplexityClassifier, TranscriptionProvider
from app.repositories.lectures import LectureRepository, ProcessingJobRepository
from app.schemas.media import AudioChunk
from app.services.media import MediaService
from app.services.profile import PlaybackProfileService

logger = logging.getLogger(__name__)


class LectureProcessingService:
    stages = (
        (ProcessingStage.INSPECTING_MEDIA, 15),
        (ProcessingStage.EXTRACTING_AUDIO, 30),
        (ProcessingStage.TRANSCRIBING, 50),
        (ProcessingStage.SEGMENTING, 65),
        (ProcessingStage.CLASSIFYING, 80),
        (ProcessingStage.GENERATING_PROFILE, 95),
    )

    def __init__(
        self,
        session: Session,
        settings: Settings,
        transcription: TranscriptionProvider,
        classifier: ComplexityClassifier,
    ) -> None:
        self.session = session
        self.settings = settings
        self.lectures = LectureRepository(session)
        self.jobs = ProcessingJobRepository(session)
        self.transcription = transcription
        self.classifier = classifier
        self.profiles = PlaybackProfileService(settings)
        self.media = MediaService(settings)

    def process(self, job_id: str, request_id: str | None = None) -> None:
        job = self.jobs.get(job_id)
        if job is None:
            return
        lecture_id = job.lecture_id
        request_id = request_id or str(uuid4())
        provider = (
            f"transcription:{self.transcription.provider_name},"
            f"classification:{self.classifier.provider_name}"
        )
        started = time.monotonic()
        audio_chunks: list[AudioChunk] = []
        try:
            for stage, progress in self.stages:
                job.mark_processing(stage, progress)
                self.session.commit()
                logger.info(
                    "lecture processing stage started",
                    extra={
                        "lecture_id": job.lecture_id,
                        "job_id": job.id,
                        "request_id": request_id,
                        "processing_stage": stage.value,
                        "provider": provider,
                    },
                )
                if self.settings.mock_stage_delay_seconds:
                    time.sleep(self.settings.mock_stage_delay_seconds)
                if stage == ProcessingStage.EXTRACTING_AUDIO:
                    lecture = job.lecture
                    if self.transcription.provider_name == "mock":
                        audio_chunks = [
                            AudioChunk(
                                path=Path(lecture.media_path),
                                start_offset_seconds=0,
                                duration_seconds=lecture.duration_seconds,
                                temporary=False,
                            )
                        ]
                    else:
                        audio_chunks = self.media.extract_audio(
                            Path(lecture.media_path), lecture.duration_seconds
                        )
                elif stage == ProcessingStage.TRANSCRIBING:
                    lecture = job.lecture
                    try:
                        transcript = self.transcription.transcribe(audio_chunks)
                    finally:
                        self.media.cleanup_audio(audio_chunks)
                        audio_chunks = []
                    lecture.transcript = [item.model_dump(mode="json") for item in transcript]
                elif stage == ProcessingStage.CLASSIFYING:
                    results = self.classifier.classify(transcript)
                elif stage == ProcessingStage.GENERATING_PROFILE:
                    profile = self.profiles.generate(results)
                    job.lecture.playback_profile = [
                        item.model_dump(mode="json") for item in profile
                    ]
                self.session.commit()
            job.mark_completed()
            self.session.commit()
            logger.info(
                "lecture processing completed",
                extra={
                    "lecture_id": job.lecture_id,
                    "job_id": job.id,
                    "request_id": request_id,
                    "processing_stage": job.stage,
                    "provider": provider,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )
        except Exception as error:
            self.session.rollback()
            job = self.jobs.get(job_id)
            if job is None:
                logger.info(
                    "lecture processing cancelled after deletion",
                    extra={
                        "lecture_id": lecture_id,
                        "job_id": job_id,
                        "request_id": request_id,
                        "provider": provider,
                    },
                )
                return
            if job:
                if isinstance(error, ApplicationError):
                    job.mark_failed(error.code, error.message)
                else:
                    job.mark_failed(
                        "PROCESSING_FAILED", "Lecture processing failed. Please try again."
                    )
                self.session.commit()
            logger.exception(
                "lecture processing failed",
                extra={
                    "lecture_id": job.lecture_id if job else None,
                    "job_id": job_id,
                    "request_id": request_id,
                    "processing_stage": job.stage if job else None,
                    "provider": provider,
                },
            )
            raise error
        finally:
            self.media.cleanup_audio(audio_chunks)
