import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.db.session import Base
from app.models.lecture import Lecture, ProcessingJob, ProcessingStatus
from app.models.user import User
from app.providers.mock import MockComplexityClassifier, MockTranscriptionProvider
from app.schemas.lecture import TranscriptSegment
from app.schemas.media import AudioChunk
from app.services.processing import LectureProcessingService


def test_mock_processing_completes_with_transcript_and_profile(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="processing@example.com", password_hash="unused")
        session.add(user)
        session.flush()
        lecture = Lecture(
            user_id=user.id,
            title="Systems lecture",
            original_filename="lecture.mp4",
            media_path=str(tmp_path / "lecture.mp4"),
            media_type="video/mp4",
            media_hash="a" * 64,
            file_size_bytes=10,
            duration_seconds=80,
        )
        session.add(lecture)
        session.flush()
        job = ProcessingJob(lecture_id=lecture.id)
        session.add(job)
        session.commit()

        config = Settings(media_storage_path=tmp_path, mock_stage_delay_seconds=0)
        caplog.set_level(logging.INFO, logger="app.services.processing")
        LectureProcessingService(
            session,
            config,
            MockTranscriptionProvider(),
            MockComplexityClassifier(),
        ).process(job.id, request_id="request-123")

        session.refresh(job)
        session.refresh(lecture)
        assert job.status == ProcessingStatus.COMPLETED
        assert job.progress == 100
        assert len(lecture.transcript or []) == 4
        assert [item["playback_rate"] for item in lecture.playback_profile or []] == [
            2.0,
            1.0,
            1.5,
        ]
        stage_records = [
            record
            for record in caplog.records
            if record.message == "lecture processing stage started"
        ]
        assert [record.processing_stage for record in stage_records] == [
            stage.value for stage, _ in LectureProcessingService.stages
        ]
        assert all(
            record.provider == "transcription:mock,classification:mock" for record in stage_records
        )


class FailingTranscriptionProvider:
    provider_name = "openai"

    def transcribe(self, audio_chunks: list[AudioChunk]) -> list[TranscriptSegment]:
        assert audio_chunks
        raise ApplicationError("TRANSCRIPTION_FAILED", "Transcription failed.")


def test_processing_cleans_audio_when_transcription_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="failure@example.com", password_hash="unused")
        session.add(user)
        session.flush()
        video_path = tmp_path / "lecture.mp4"
        video_path.write_bytes(b"video")
        audio_path = tmp_path / "audio" / "job" / "chunk-00000.m4a"
        audio_path.parent.mkdir(parents=True)
        audio_path.write_bytes(b"audio")
        lecture = Lecture(
            user_id=user.id,
            title="Systems lecture",
            original_filename="lecture.mp4",
            media_path=str(video_path),
            media_type="video/mp4",
            media_hash="b" * 64,
            file_size_bytes=5,
            duration_seconds=1500,
        )
        session.add(lecture)
        session.flush()
        job = ProcessingJob(lecture_id=lecture.id)
        session.add(job)
        session.commit()
        service = LectureProcessingService(
            session,
            Settings(_env_file=None, media_storage_path=tmp_path, mock_stage_delay_seconds=0),
            FailingTranscriptionProvider(),
            MockComplexityClassifier(),
        )
        monkeypatch.setattr(
            service.media,
            "extract_audio",
            lambda *_: [AudioChunk(path=audio_path, start_offset_seconds=0, duration_seconds=1200)],
        )

        with pytest.raises(ApplicationError):
            service.process(job.id)

        session.refresh(job)
        assert job.status == ProcessingStatus.FAILED
        assert job.error_code == "TRANSCRIPTION_FAILED"
        assert not audio_path.exists()


class DeletingTranscriptionProvider:
    provider_name = "mock"

    def __init__(self, engine: Engine, job_id: str, lecture_id: str) -> None:
        self.engine = engine
        self.job_id = job_id
        self.lecture_id = lecture_id

    def transcribe(self, audio_chunks: list[AudioChunk]) -> list[TranscriptSegment]:
        assert audio_chunks
        with Session(self.engine) as deleting_session:
            job = deleting_session.get(ProcessingJob, self.job_id)
            lecture = deleting_session.get(Lecture, self.lecture_id)
            assert job is not None
            assert lecture is not None
            deleting_session.delete(job)
            deleting_session.delete(lecture)
            deleting_session.commit()
        return [TranscriptSegment(start_seconds=0, end_seconds=30, text="Deleted lecture")]


def test_processing_stops_cleanly_when_lecture_is_deleted_mid_job(tmp_path: Path) -> None:
    database_path = tmp_path / "processing-deletion.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    video_path = tmp_path / "deleting.mp4"
    video_path.write_bytes(b"video")

    with Session(engine) as session:
        user = User(email="delete-processing@example.com", password_hash="unused")
        session.add(user)
        session.flush()
        lecture = Lecture(
            user_id=user.id,
            title="Deleting lecture",
            original_filename="deleting.mp4",
            media_path=str(video_path),
            media_type="video/mp4",
            media_hash="c" * 64,
            file_size_bytes=5,
            duration_seconds=60,
        )
        session.add(lecture)
        session.flush()
        job = ProcessingJob(lecture_id=lecture.id)
        session.add(job)
        session.commit()
        job_id = job.id
        lecture_id = lecture.id
        service = LectureProcessingService(
            session,
            Settings(_env_file=None, media_storage_path=tmp_path, mock_stage_delay_seconds=0),
            DeletingTranscriptionProvider(engine, job_id, lecture_id),
            MockComplexityClassifier(),
        )

        service.process(job_id)

    with Session(engine) as session:
        assert session.get(ProcessingJob, job_id) is None
        assert session.get(Lecture, lecture_id) is None
