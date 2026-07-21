from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import load_only, selectinload

from app.models.lecture import Lecture, ProcessingJob


class LectureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, lecture: Lecture) -> Lecture:
        self.session.add(lecture)
        self.session.flush()
        return lecture

    def get(self, lecture_id: str, user_id: str) -> Lecture | None:
        return self.session.scalar(
            select(Lecture).where(Lecture.id == lecture_id, Lecture.user_id == user_id)
        )

    def get_by_media_hash(self, user_id: str, media_hash: str) -> Lecture | None:
        return self.session.scalar(
            select(Lecture).where(
                Lecture.user_id == user_id,
                Lecture.media_hash == media_hash,
            )
        )

    def delete(self, lecture: Lecture) -> None:
        self.session.delete(lecture)

    def list(self, user_id: str, limit: int, offset: int) -> list[Lecture]:
        statement = (
            select(Lecture)
            .options(
                load_only(
                    Lecture.id,
                    Lecture.title,
                    Lecture.duration_seconds,
                    Lecture.created_at,
                ),
                selectinload(Lecture.job).load_only(ProcessingJob.status),
            )
            .where(Lecture.user_id == user_id)
            .order_by(Lecture.created_at.desc(), Lecture.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))


class ProcessingJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, job: ProcessingJob) -> ProcessingJob:
        self.session.add(job)
        self.session.flush()
        return job

    def get(self, job_id: str) -> ProcessingJob | None:
        return self.session.get(ProcessingJob, job_id)

    def delete(self, job: ProcessingJob) -> None:
        self.session.delete(job)
