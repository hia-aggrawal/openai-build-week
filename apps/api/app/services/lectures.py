from pathlib import Path
from urllib.parse import urlencode

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError, LectureNotFoundError
from app.core.signing import VideoLinkSigner
from app.models.lecture import Lecture, ProcessingJob, ProcessingStatus
from app.providers.interfaces import JobDispatcher
from app.repositories.lectures import LectureRepository, ProcessingJobRepository
from app.schemas.lecture import (
    JobResponse,
    LectureCreatedResponse,
    LectureListResponse,
    LectureResponse,
    LectureSummaryResponse,
)
from app.services.media import MediaService


class LectureService:
    def __init__(
        self,
        session: Session,
        media: MediaService,
        dispatcher: JobDispatcher,
        video_signer: VideoLinkSigner,
        user_id: str,
    ) -> None:
        self.session = session
        self.media = media
        self.dispatcher = dispatcher
        self.video_signer = video_signer
        self.user_id = user_id
        self.lectures = LectureRepository(session)
        self.jobs = ProcessingJobRepository(session)

    def create(
        self,
        upload: UploadFile,
        title: str,
        duration_seconds: float,
        request_id: str | None = None,
    ) -> LectureCreatedResponse:
        path, size, media_hash = self.media.save_upload(upload)
        return self.create_from_file(
            path=path,
            size=size,
            content_type=upload.content_type or "application/octet-stream",
            original_filename=upload.filename or "lecture",
            title=title,
            duration_seconds=duration_seconds,
            media_hash=media_hash,
            request_id=request_id,
        )

    def create_from_file(
        self,
        path: Path,
        size: int,
        content_type: str,
        original_filename: str,
        title: str,
        duration_seconds: float,
        media_hash: str,
        request_id: str | None = None,
    ) -> LectureCreatedResponse:
        existing = self.lectures.get_by_media_hash(self.user_id, media_hash)
        if existing is not None:
            path.unlink(missing_ok=True)
            return LectureCreatedResponse(
                lecture_id=existing.id,
                job_id=existing.job.id,
                status=existing.job.status,
                duplicate=True,
            )
        try:
            inspected_duration = self.media.inspect_duration(path, duration_seconds)
            lecture = self.lectures.add(
                Lecture(
                    user_id=self.user_id,
                    title=title.strip() or Path(original_filename).stem,
                    original_filename=original_filename[:255],
                    media_path=str(path.resolve()),
                    media_type=content_type,
                    media_hash=media_hash,
                    file_size_bytes=size,
                    duration_seconds=inspected_duration,
                )
            )
            job = self.jobs.add(ProcessingJob(lecture_id=lecture.id))
            self.session.commit()
        except Exception:
            path.unlink(missing_ok=True)
            self.session.rollback()
            raise
        self.dispatcher.dispatch(job.id, request_id=request_id)
        return LectureCreatedResponse(lecture_id=lecture.id, job_id=job.id, status=job.status)

    def delete(self, lecture_id: str) -> None:
        lecture = self.lectures.get(lecture_id, self.user_id)
        if lecture is None:
            raise LectureNotFoundError()
        media_path = Path(lecture.media_path)
        if lecture.job is not None:
            self.jobs.delete(lecture.job)
        self.lectures.delete(lecture)
        self.session.commit()
        media_path.unlink(missing_ok=True)

    def retry(self, lecture_id: str, request_id: str | None = None) -> LectureCreatedResponse:
        lecture = self.lectures.get(lecture_id, self.user_id)
        if lecture is None:
            raise LectureNotFoundError()
        job = lecture.job
        if job.status != ProcessingStatus.FAILED:
            raise ApplicationError(
                "LECTURE_NOT_FAILED",
                "Only failed lectures can be retried.",
                409,
            )
        job.reset_for_retry()
        self.session.commit()
        self.dispatcher.dispatch(job.id, request_id=request_id)
        return LectureCreatedResponse(lecture_id=lecture.id, job_id=job.id, status=job.status)

    def get(self, lecture_id: str) -> LectureResponse:
        lecture = self.lectures.get(lecture_id, self.user_id)
        if lecture is None:
            raise LectureNotFoundError()
        signed_video = self.video_signer.issue(lecture.id)
        video_query = urlencode({"expires": signed_video.expires, "token": signed_video.token})
        return LectureResponse(
            id=lecture.id,
            title=lecture.title,
            duration_seconds=lecture.duration_seconds,
            video_url=f"/api/lectures/{lecture.id}/video?{video_query}",
            captions_url=f"/api/lectures/{lecture.id}/captions.vtt",
            job=JobResponse.model_validate(lecture.job),
            transcript=lecture.transcript,
            playback_profile=lecture.playback_profile,
        )

    def list(self, limit: int, offset: int) -> LectureListResponse:
        lectures = self.lectures.list(self.user_id, limit=limit + 1, offset=offset)
        has_more = len(lectures) > limit
        page = lectures[:limit]
        return LectureListResponse(
            items=[
                LectureSummaryResponse(
                    id=lecture.id,
                    title=lecture.title,
                    duration_seconds=lecture.duration_seconds,
                    created_at=lecture.created_at,
                    job_status=lecture.job.status,
                )
                for lecture in page
            ],
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
        )
