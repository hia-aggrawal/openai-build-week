from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.core.time import utc_now
from app.models.user import User


class ProcessingStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingStage(StrEnum):
    VALIDATING = "VALIDATING"
    INSPECTING_MEDIA = "INSPECTING_MEDIA"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    SEGMENTING = "SEGMENTING"
    CLASSIFYING = "CLASSIFYING"
    GENERATING_PROFILE = "GENERATING_PROFILE"


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (Index("ix_lectures_user_media_hash", "user_id", "media_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    media_path: Mapped[str] = mapped_column(String(1024), unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    media_hash: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float] = mapped_column(Float)
    transcript: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    playback_profile: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    job: Mapped["ProcessingJob"] = relationship(back_populates="lecture", uselist=False)
    user: Mapped["User"] = relationship(back_populates="lectures")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lecture_id: Mapped[str] = mapped_column(ForeignKey("lectures.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=ProcessingStatus.QUEUED, index=True)
    stage: Mapped[str] = mapped_column(String(40), default=ProcessingStage.VALIDATING)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lecture: Mapped[Lecture] = relationship(back_populates="job")

    def mark_processing(self, stage: ProcessingStage, progress: int) -> None:
        self.status = ProcessingStatus.PROCESSING
        self.stage = stage
        self.progress = progress
        self.updated_at = utc_now()

    def mark_completed(self) -> None:
        self.status = ProcessingStatus.COMPLETED
        self.stage = ProcessingStage.GENERATING_PROFILE
        self.progress = 100
        self.updated_at = utc_now()

    def mark_failed(self, code: str, message: str) -> None:
        self.status = ProcessingStatus.FAILED
        self.error_code = code
        self.error_message = message
        self.updated_at = utc_now()

    def reset_for_retry(self) -> None:
        self.status = ProcessingStatus.QUEUED
        self.stage = ProcessingStage.VALIDATING
        self.progress = 0
        self.error_code = None
        self.error_message = None
        self.updated_at = utc_now()
