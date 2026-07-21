from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.core.auth import set_session_cookie
from app.core.config import settings
from app.core.errors import ApplicationError
from app.core.logging import configure_logging
from app.services.media import MediaService
from app.services.uploads import ChunkedUploadService

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    settings.media_storage_path.mkdir(parents=True, exist_ok=True)
    removed_uploads = ChunkedUploadService.cleanup_stale(MediaService(settings))
    if removed_uploads:
        logger.info("stale uploads removed", extra={"result_count": removed_uploads})
    yield


app = FastAPI(title="StudyFlow API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(auth_router)
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = str(uuid4())
    request.state.request_id = request_id
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "api request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    renewed_session_token = getattr(request.state, "renewed_session_token", None)
    if renewed_session_token is not None:
        set_session_cookie(response, renewed_session_token, settings)
    logger.info(
        "api request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
    )
    return response


@app.exception_handler(ApplicationError)
def handle_application_error(request: Request, error: ApplicationError) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )
