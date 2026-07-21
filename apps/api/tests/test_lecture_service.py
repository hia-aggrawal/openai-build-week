from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.signing import VideoLinkSigner
from app.db.session import Base
from app.models.lecture import Lecture, ProcessingJob
from app.models.user import User
from app.services.lectures import LectureService
from app.services.media import MediaService


class RecordingDispatcher:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    def dispatch(self, job_id: str, request_id: str | None = None) -> None:
        self.job_ids.append(job_id)


def make_upload(content: bytes) -> UploadFile:
    return UploadFile(
        filename="lecture.mp4",
        file=BytesIO(content),
        headers={"content-type": "video/mp4"},
    )


def make_service(
    session: Session,
    tmp_path: Path,
    dispatcher: RecordingDispatcher,
    user_id: str,
) -> LectureService:
    settings = Settings(_env_file=None, media_storage_path=tmp_path, processing_mode="mock")
    return LectureService(
        session,
        MediaService(settings),
        dispatcher,
        VideoLinkSigner("duplicate-test-secret", ttl_seconds=60),
        user_id,
    )


def test_identical_upload_for_same_user_reuses_lecture_and_job(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    dispatcher = RecordingDispatcher()

    with Session(engine) as session:
        user = User(email="duplicate@example.com", password_hash="unused")
        session.add(user)
        session.commit()
        service = make_service(session, tmp_path, dispatcher, user.id)

        first = service.create(make_upload(b"identical video"), "First title", 60)
        second = service.create(make_upload(b"identical video"), "Second title", 60)

        assert second.duplicate is True
        assert second.lecture_id == first.lecture_id
        assert second.job_id == first.job_id
        assert session.scalar(select(func.count()).select_from(Lecture)) == 1
        assert session.scalar(select(func.count()).select_from(ProcessingJob)) == 1
        assert dispatcher.job_ids == [first.job_id]
        assert len(list(tmp_path.glob("*.mp4"))) == 1


def test_identical_upload_for_different_users_creates_separate_lectures(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    dispatcher = RecordingDispatcher()

    with Session(engine) as session:
        first_user = User(email="first@example.com", password_hash="unused")
        second_user = User(email="second@example.com", password_hash="unused")
        session.add_all((first_user, second_user))
        session.commit()

        first = make_service(session, tmp_path, dispatcher, first_user.id).create(
            make_upload(b"shared public video"), "First", 60
        )
        second = make_service(session, tmp_path, dispatcher, second_user.id).create(
            make_upload(b"shared public video"), "Second", 60
        )

        assert first.lecture_id != second.lecture_id
        assert second.duplicate is False
        assert session.scalar(select(func.count()).select_from(Lecture)) == 2
        assert session.scalar(select(func.count()).select_from(ProcessingJob)) == 2
        assert dispatcher.job_ids == [first.job_id, second.job_id]
