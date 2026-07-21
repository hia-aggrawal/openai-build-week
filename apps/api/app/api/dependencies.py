from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import SESSION_COOKIE_NAME
from app.core.config import settings
from app.core.signing import VideoLinkSigner
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.providers.interfaces import ComplexityClassifier, JobDispatcher, TranscriptionProvider
from app.providers.mock import MockComplexityClassifier, MockTranscriptionProvider
from app.providers.openai import OpenAIComplexityClassifier, OpenAITranscriptionProvider
from app.services.lectures import LectureService
from app.services.auth import AuthService
from app.services.media import MediaService
from app.services.processing import LectureProcessingService
from app.services.uploads import ChunkedUploadService
from app.workers.celery_app import celery_app
from app.workers.dispatcher import CeleryJobDispatcher, InProcessJobDispatcher


def openai_api_key() -> str:
    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI providers.")
    return settings.openai_api_key.get_secret_value()


def build_transcription_provider() -> TranscriptionProvider:
    if settings.transcription_provider == "openai":
        return OpenAITranscriptionProvider(openai_api_key(), settings.transcription_model)
    return MockTranscriptionProvider()


def build_complexity_classifier() -> ComplexityClassifier:
    if settings.classification_provider == "openai":
        return OpenAIComplexityClassifier(openai_api_key(), settings.classification_model)
    return MockComplexityClassifier()


def process_job(job_id: str, request_id: str | None = None) -> None:
    with SessionLocal() as session:
        LectureProcessingService(
            session,
            settings,
            build_transcription_provider(),
            build_complexity_classifier(),
        ).process(job_id, request_id=request_id)


@lru_cache
def get_dispatcher() -> JobDispatcher:
    if settings.processing_mode == "celery":
        return CeleryJobDispatcher(celery_app)
    return InProcessJobDispatcher(process_job)


@lru_cache
def get_video_link_signer() -> VideoLinkSigner:
    if settings.video_link_ttl_seconds <= 0:
        raise RuntimeError("VIDEO_LINK_TTL_SECONDS must be positive.")
    return VideoLinkSigner(settings.secret_key.get_secret_value(), settings.video_link_ttl_seconds)


def build_auth_service(session: Session) -> AuthService:
    return AuthService(session, settings)


def get_current_user(request: Request, session: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = build_auth_service(session).authenticate(token)
    request.state.user_id = user.id
    if token is not None:
        request.state.renewed_session_token = token
    return user


def build_lecture_service(session: Session, user_id: str) -> LectureService:
    return LectureService(
        session,
        MediaService(settings),
        get_dispatcher(),
        get_video_link_signer(),
        user_id,
    )


def build_chunked_upload_service(session: Session, user_id: str) -> ChunkedUploadService:
    media = MediaService(settings)
    lecture_service = LectureService(
        session, media, get_dispatcher(), get_video_link_signer(), user_id
    )
    return ChunkedUploadService(media, lecture_service)
