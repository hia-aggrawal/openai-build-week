from pathlib import Path
import logging

from fastapi import APIRouter, Body, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    build_chunked_upload_service,
    build_lecture_service,
    get_current_user,
    get_video_link_signer,
)
from app.core.errors import LectureNotFoundError
from app.core.signing import VideoLinkSigner
from app.db.session import get_db
from app.repositories.lectures import LectureRepository
from app.models.user import User
from app.schemas.lecture import (
    LectureCreatedResponse,
    LectureListResponse,
    LectureResponse,
    UploadCompleteRequest,
    UploadSessionCreatedResponse,
    UploadSessionCreateRequest,
)
from app.services.uploads import ChunkedUploadService

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _webvtt_timestamp(seconds: float) -> str:
    total_milliseconds = round(seconds * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _build_webvtt(transcript: list[dict] | None) -> str:
    cues = ["WEBVTT", ""]
    for index, segment in enumerate(transcript or [], start=1):
        cues.extend(
            (
                str(index),
                f"{_webvtt_timestamp(float(segment['start_seconds']))} --> "
                f"{_webvtt_timestamp(float(segment['end_seconds']))}",
                str(segment["text"]),
                "",
            )
        )
    return "\n".join(cues)


def get_chunked_upload_service(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChunkedUploadService:
    return build_chunked_upload_service(session, user.id)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/lectures", response_model=LectureCreatedResponse, status_code=202)
def create_lecture(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    duration_seconds: float = Form(..., gt=0),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureCreatedResponse:
    result = build_lecture_service(session, user.id).create(
        file, title, duration_seconds, request_id=request.state.request_id
    )
    logger.info(
        "lecture upload accepted",
        extra={
            "request_id": request.state.request_id,
            "lecture_id": result.lecture_id,
            "job_id": result.job_id,
        },
    )
    return result


@router.post("/lectures/uploads", response_model=UploadSessionCreatedResponse, status_code=201)
def start_lecture_upload(
    upload: UploadSessionCreateRequest,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadSessionCreatedResponse:
    return build_chunked_upload_service(session, user.id).start(
        filename=upload.filename,
        content_type=upload.content_type,
        total_size=upload.total_size,
        chunk_size=upload.chunk_size,
        user_id=user.id,
    )


@router.put("/lectures/uploads/{upload_id}/chunks/{index}", status_code=204)
def upload_lecture_chunk(
    upload_id: str,
    index: int,
    content: bytes = Body(..., media_type="application/octet-stream"),
    service: ChunkedUploadService = Depends(get_chunked_upload_service),
    user: User = Depends(get_current_user),
) -> None:
    service.write_chunk(upload_id, index, content, user.id)


@router.post(
    "/lectures/uploads/{upload_id}/complete",
    response_model=LectureCreatedResponse,
    status_code=202,
)
def complete_lecture_upload(
    upload_id: str,
    upload: UploadCompleteRequest,
    request: Request,
    service: ChunkedUploadService = Depends(get_chunked_upload_service),
    user: User = Depends(get_current_user),
) -> LectureCreatedResponse:
    result = service.complete(
        upload_id=upload_id,
        title=upload.title,
        duration_seconds=upload.duration_seconds,
        user_id=user.id,
        request_id=request.state.request_id,
    )
    logger.info(
        "chunked lecture upload completed",
        extra={
            "request_id": request.state.request_id,
            "lecture_id": result.lecture_id,
            "job_id": result.job_id,
        },
    )
    return result


@router.get("/lectures", response_model=LectureListResponse)
def list_lectures(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureListResponse:
    result = build_lecture_service(session, user.id).list(limit=limit, offset=offset)
    logger.info(
        "lectures listed",
        extra={
            "request_id": request.state.request_id,
            "limit": limit,
            "offset": offset,
            "result_count": len(result.items),
        },
    )
    return result


@router.get("/lectures/{lecture_id}", response_model=LectureResponse)
def get_lecture(
    lecture_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureResponse:
    result = build_lecture_service(session, user.id).get(lecture_id)
    logger.info(
        "lecture retrieved",
        extra={"request_id": request.state.request_id, "lecture_id": lecture_id},
    )
    return result


@router.delete("/lectures/{lecture_id}", status_code=204)
def delete_lecture(
    lecture_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    build_lecture_service(session, user.id).delete(lecture_id)
    logger.info(
        "lecture deleted",
        extra={"request_id": request.state.request_id, "lecture_id": lecture_id},
    )


@router.post("/lectures/{lecture_id}/retry", response_model=LectureCreatedResponse, status_code=202)
def retry_lecture(
    lecture_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureCreatedResponse:
    result = build_lecture_service(session, user.id).retry(
        lecture_id, request_id=request.state.request_id
    )
    logger.info(
        "lecture retry dispatched",
        extra={
            "request_id": request.state.request_id,
            "lecture_id": lecture_id,
            "job_id": result.job_id,
        },
    )
    return result


@router.get("/lectures/{lecture_id}/captions.vtt")
def get_captions(
    lecture_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    lecture = LectureRepository(session).get(lecture_id, user.id)
    if lecture is None:
        raise LectureNotFoundError()
    logger.info(
        "lecture captions requested",
        extra={"request_id": request.state.request_id, "lecture_id": lecture_id},
    )
    return Response(_build_webvtt(lecture.transcript), media_type="text/vtt")


@router.get("/lectures/{lecture_id}/video")
def get_video(
    lecture_id: str,
    request: Request,
    expires: int | None = None,
    token: str | None = None,
    session: Session = Depends(get_db),
    signer: VideoLinkSigner = Depends(get_video_link_signer),
    user: User = Depends(get_current_user),
) -> FileResponse:
    signer.verify(lecture_id, expires, token)
    lecture = LectureRepository(session).get(lecture_id, user.id)
    if lecture is None:
        raise LectureNotFoundError()
    logger.info(
        "lecture video requested",
        extra={"request_id": request.state.request_id, "lecture_id": lecture_id},
    )
    return FileResponse(Path(lecture.media_path), media_type=lecture.media_type, filename=None)
