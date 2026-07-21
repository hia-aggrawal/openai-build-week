from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.lecture import Lecture, ProcessingJob
from app.models.user import User
from app.repositories.lectures import LectureRepository, ProcessingJobRepository


def test_lecture_and_processing_job_repository_queries(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="repository@example.com", password_hash="unused")
        session.add(user)
        session.flush()
        lectures = LectureRepository(session)
        jobs = ProcessingJobRepository(session)
        lecture = lectures.add(
            Lecture(
                user_id=user.id,
                title="Repository lecture",
                original_filename="lecture.mp4",
                media_path=str(tmp_path / "lecture.mp4"),
                media_type="video/mp4",
                media_hash="a" * 64,
                file_size_bytes=100,
                duration_seconds=60,
            )
        )
        job = jobs.add(ProcessingJob(lecture_id=lecture.id))
        session.commit()

        assert lectures.get(lecture.id, user.id) is lecture
        assert jobs.get(job.id) is job
        assert lectures.get("missing", user.id) is None
        assert jobs.get("missing") is None


def test_lecture_repository_lists_newest_first_with_pagination(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="list@example.com", password_hash="unused")
        session.add(user)
        session.flush()
        for index, title in enumerate(("Oldest", "Middle", "Newest"), start=1):
            lecture = Lecture(
                user_id=user.id,
                title=title,
                original_filename=f"lecture-{index}.mp4",
                media_path=str(tmp_path / f"lecture-{index}.mp4"),
                media_type="video/mp4",
                media_hash=f"{index:064x}",
                file_size_bytes=100,
                duration_seconds=60,
                created_at=datetime(2026, 1, index, tzinfo=timezone.utc),
                transcript=[{"text": "must not be selected"}],
                playback_profile=[{"playback_rate": 1}],
            )
            session.add(lecture)
            session.flush()
            session.add(ProcessingJob(lecture_id=lecture.id))
        session.commit()

    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "list@example.com"))
        assert user is not None
        page = LectureRepository(session).list(user.id, limit=1, offset=1)

        assert [lecture.title for lecture in page] == ["Middle"]
        assert page[0].job.status == "QUEUED"
        assert "transcript" in inspect(page[0]).unloaded
        assert "playback_profile" in inspect(page[0]).unloaded
