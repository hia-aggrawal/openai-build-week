import json
import shutil
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import ceil
from pathlib import Path
from uuid import UUID, uuid4

from app.core.errors import ApplicationError, UploadSessionNotFoundError
from app.schemas.lecture import LectureCreatedResponse, UploadSessionCreatedResponse
from app.services.lectures import LectureService
from app.services.media import MediaService

STALE_UPLOAD_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class UploadSession:
    upload_id: str
    filename: str
    content_type: str
    total_size: int
    chunk_size: int
    chunk_count: int
    user_id: str


class ChunkedUploadService:
    def __init__(self, media: MediaService, lectures: LectureService) -> None:
        self.media = media
        self.lectures = lectures
        self.upload_root = media.settings.media_storage_path / "uploads"

    def start(
        self,
        filename: str,
        content_type: str,
        total_size: int,
        chunk_size: int,
        user_id: str,
    ) -> UploadSessionCreatedResponse:
        self.media.validate_upload(filename, content_type, total_size)
        if chunk_size > self.media.maximum_upload_bytes:
            raise ApplicationError("INVALID_CHUNK_SIZE", "The requested chunk size is too large.")
        upload_id = str(uuid4())
        session = UploadSession(
            upload_id=upload_id,
            filename=Path(filename).name,
            content_type=content_type,
            total_size=total_size,
            chunk_size=chunk_size,
            chunk_count=ceil(total_size / chunk_size),
            user_id=user_id,
        )
        session_directory = self._session_directory(upload_id)
        session_directory.mkdir(parents=True)
        (session_directory / "session.json").write_text(json.dumps(asdict(session)))
        return UploadSessionCreatedResponse(
            upload_id=upload_id, expected_chunk_count=session.chunk_count
        )

    def write_chunk(self, upload_id: str, index: int, content: bytes, user_id: str) -> None:
        session = self._load_for_user(upload_id, user_id)
        if index < 0 or index >= session.chunk_count:
            raise ApplicationError("INVALID_CHUNK_INDEX", "The chunk index is out of range.")
        expected_size = min(session.chunk_size, session.total_size - (index * session.chunk_size))
        if len(content) != expected_size:
            raise ApplicationError("INVALID_CHUNK_SIZE", "The chunk has an unexpected size.")
        (self._session_directory(upload_id) / str(index)).write_bytes(content)

    def complete(
        self,
        upload_id: str,
        title: str,
        duration_seconds: float,
        user_id: str,
        request_id: str | None = None,
    ) -> LectureCreatedResponse:
        session = self._load_for_user(upload_id, user_id)
        session_directory = self._session_directory(upload_id)
        chunk_paths = [session_directory / str(index) for index in range(session.chunk_count)]
        if any(not path.is_file() for path in chunk_paths):
            raise ApplicationError("CHUNK_MISSING", "One or more upload chunks are missing.")

        suffix = self.media.validate_upload(
            session.filename, session.content_type, session.total_size
        )
        self.media.settings.media_storage_path.mkdir(parents=True, exist_ok=True)
        destination = self.media.settings.media_storage_path / f"{uuid4()}{suffix}"
        digest = sha256()
        try:
            with destination.open("wb") as output:
                for chunk_path in chunk_paths:
                    with chunk_path.open("rb") as chunk:
                        while content := chunk.read(1024 * 1024):
                            output.write(content)
                            digest.update(content)
            if destination.stat().st_size != session.total_size:
                raise ApplicationError(
                    "UPLOAD_SIZE_MISMATCH", "The completed upload size is invalid."
                )
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        shutil.rmtree(session_directory)
        return self.lectures.create_from_file(
            path=destination,
            size=session.total_size,
            content_type=session.content_type,
            original_filename=session.filename,
            title=title,
            duration_seconds=duration_seconds,
            media_hash=digest.hexdigest(),
            request_id=request_id,
        )

    def _load(self, upload_id: str) -> UploadSession:
        metadata_path = self._session_directory(upload_id) / "session.json"
        try:
            return UploadSession(**json.loads(metadata_path.read_text()))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            raise UploadSessionNotFoundError() from None

    def _load_for_user(self, upload_id: str, user_id: str) -> UploadSession:
        session = self._load(upload_id)
        if session.user_id != user_id:
            raise UploadSessionNotFoundError()
        return session

    def _session_directory(self, upload_id: str) -> Path:
        try:
            normalized_id = str(UUID(upload_id))
        except ValueError:
            raise UploadSessionNotFoundError() from None
        return self.upload_root / normalized_id

    @staticmethod
    def cleanup_stale(media: MediaService, now: float | None = None) -> int:
        upload_root = media.settings.media_storage_path / "uploads"
        if not upload_root.exists():
            return 0
        cutoff = (now if now is not None else time.time()) - STALE_UPLOAD_SECONDS
        stale = [
            path
            for path in upload_root.iterdir()
            if path.is_dir() and path.stat().st_mtime < cutoff
        ]
        for path in stale:
            shutil.rmtree(path)
        return len(stale)
