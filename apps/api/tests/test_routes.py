from collections.abc import Generator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.config import Settings
from app.core.signing import VideoLinkSigner
from app.db.session import Base, get_db
from app.main import app
from app.models.lecture import Lecture, ProcessingJob, ProcessingStatus
from app.services.lectures import LectureService
from app.services.media import MediaService
from app.services.uploads import ChunkedUploadService


class RecordingDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[tuple[str, str | None]] = []

    def dispatch(self, job_id: str, request_id: str | None = None) -> None:
        self.dispatched.append((job_id, request_id))


@pytest.fixture
def route_database() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def route_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_database: sessionmaker[Session],
) -> Generator[tuple[TestClient, RecordingDispatcher, VideoLinkSigner], None, None]:
    test_settings = Settings(
        _env_file=None,
        media_storage_path=tmp_path,
        processing_mode="mock",
        transcription_provider="mock",
        classification_provider="mock",
        max_upload_size_mb=1,
    )
    dispatcher = RecordingDispatcher()
    signer = VideoLinkSigner("route-test-secret", ttl_seconds=4 * 60 * 60)

    def override_db() -> Generator[Session, None, None]:
        with route_database() as session:
            yield session

    def build_service(session: Session, user_id: str) -> LectureService:
        return LectureService(session, MediaService(test_settings), dispatcher, signer, user_id)

    def build_upload_service(session: Session, user_id: str) -> ChunkedUploadService:
        media = MediaService(test_settings)
        return ChunkedUploadService(
            media, LectureService(session, media, dispatcher, signer, user_id)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[routes.get_video_link_signer] = lambda: signer
    monkeypatch.setattr(routes, "build_lecture_service", build_service)
    monkeypatch.setattr(routes, "build_chunked_upload_service", build_upload_service)
    with TestClient(app) as client:
        signed_up = client.post(
            "/api/auth/signup",
            json={"email": "route@example.com", "password": "test-password"},
        )
        assert signed_up.status_code == 201
        yield client, dispatcher, signer
    app.dependency_overrides.clear()


def create_lecture(client: TestClient, content: bytes = b"0123456789") -> dict[str, str]:
    response = client.post(
        "/api/lectures",
        data={"title": "API lecture", "duration_seconds": "60"},
        files={"file": ("lecture.mp4", content, "video/mp4")},
    )
    assert response.status_code == 202
    return response.json()


def test_signup_login_logout_session_lifecycle(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client

    me = client.get("/api/auth/me")
    logout = client.post("/api/auth/logout")
    logged_out = client.get("/api/auth/me")
    login = client.post(
        "/api/auth/login",
        json={"email": "route@example.com", "password": "test-password"},
    )

    assert me.status_code == 200
    assert me.json()["email"] == "route@example.com"
    assert "max-age=" in me.headers["set-cookie"].lower()
    assert "httponly" in me.headers["set-cookie"].lower()
    assert logout.status_code == 204
    assert logged_out.status_code == 401
    assert logged_out.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").status_code == 200


def test_unauthenticated_lecture_request_is_rejected(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client
    client.cookies.clear()

    response = client.get("/api/lectures")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_lectures_are_scoped_to_the_authenticated_user(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client
    created = create_lecture(client)
    owner_lecture = client.get(f"/api/lectures/{created['lecture_id']}").json()
    client.post("/api/auth/logout")
    second_user = client.post(
        "/api/auth/signup",
        json={"email": "second@example.com", "password": "second-password"},
    )

    listed = client.get("/api/lectures")
    detail = client.get(f"/api/lectures/{created['lecture_id']}")
    video = client.get(owner_lecture["video_url"])
    captions = client.get(owner_lecture["captions_url"])

    assert second_user.status_code == 201
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert detail.status_code == 404
    assert video.status_code == 404
    assert captions.status_code == 404


def test_create_get_and_range_stream_video(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, dispatcher, _ = route_client

    created = create_lecture(client)
    lecture = client.get(f"/api/lectures/{created['lecture_id']}")
    video_url = lecture.json()["video_url"]
    video = client.get(video_url, headers={"Range": "bytes=2-5"})

    assert created["status"] == "QUEUED"
    assert dispatcher.dispatched[0][0] == created["job_id"]
    assert dispatcher.dispatched[0][1]
    assert lecture.status_code == 200
    assert lecture.json()["title"] == "API lecture"
    assert lecture.json()["captions_url"] == (
        f"/api/lectures/{created['lecture_id']}/captions.vtt"
    )
    parsed_video_url = urlsplit(video_url)
    video_query = parse_qs(parsed_video_url.query)
    assert parsed_video_url.path.endswith(f"/{created['lecture_id']}/video")
    assert video_query["expires"]
    assert video_query["token"]
    assert video.status_code == 206
    assert video.content == b"2345"
    assert video.headers["content-range"] == "bytes 2-5/10"
    assert lecture.headers["x-request-id"]


def test_captions_endpoint_returns_transcript_as_webvtt(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
    route_database: sessionmaker[Session],
) -> None:
    client, _, _ = route_client
    created = create_lecture(client)
    with route_database() as session:
        lecture = session.get(Lecture, created["lecture_id"])
        assert lecture is not None
        lecture.transcript = [
            {"start_seconds": 0, "end_seconds": 2.5, "text": "Welcome to the lecture."},
            {
                "start_seconds": 62.125,
                "end_seconds": 65.5,
                "text": "Now for the central idea.",
            },
        ]
        session.commit()

    detail = client.get(f"/api/lectures/{created['lecture_id']}")
    response = client.get(detail.json()["captions_url"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vtt")
    assert response.text == (
        "WEBVTT\n\n"
        "1\n"
        "00:00:00.000 --> 00:00:02.500\n"
        "Welcome to the lecture.\n\n"
        "2\n"
        "00:01:02.125 --> 00:01:05.500\n"
        "Now for the central idea.\n"
    )


def test_list_lectures_is_paginated_and_summary_only(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client
    first = create_lecture(client)
    second = create_lecture(client, b"abcdefghij")

    first_page = client.get("/api/lectures", params={"limit": 1, "offset": 0})
    second_page = client.get("/api/lectures", params={"limit": 1, "offset": 1})

    assert first_page.status_code == 200
    assert first_page.json()["limit"] == 1
    assert first_page.json()["offset"] == 0
    assert first_page.json()["next_offset"] == 1
    assert len(first_page.json()["items"]) == 1
    summary = first_page.json()["items"][0]
    assert set(summary) == {
        "id",
        "title",
        "duration_seconds",
        "created_at",
        "job_status",
    }
    assert summary["job_status"] == "QUEUED"
    assert {summary["id"], second_page.json()["items"][0]["id"]} == {
        first["lecture_id"],
        second["lecture_id"],
    }
    assert second_page.json()["next_offset"] is None


def test_missing_lecture_returns_stable_404(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, signer = route_client

    lecture_response = client.get("/api/lectures/missing")
    signed_video = signer.issue("missing")
    video_response = client.get(
        "/api/lectures/missing/video",
        params={"expires": signed_video.expires, "token": signed_video.token},
    )

    for response in (lecture_response, video_response):
        assert response.status_code == 404
        assert response.json() == {
            "error": {"code": "LECTURE_NOT_FOUND", "message": "Lecture not found."}
        }


def test_expired_video_token_is_rejected(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, signer = route_client
    created = create_lecture(client)
    expired = signer.issue(created["lecture_id"], now=0)

    response = client.get(
        f"/api/lectures/{created['lecture_id']}/video",
        params={"expires": expired.expires, "token": expired.token},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "VIDEO_LINK_EXPIRED"


def test_tampered_video_signature_is_rejected(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client
    created = create_lecture(client)
    lecture = client.get(f"/api/lectures/{created['lecture_id']}").json()
    tampered_url = lecture["video_url"].replace("token=", "token=tampered", 1)

    response = client.get(tampered_url)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_VIDEO_LINK"


def test_create_rejects_unsupported_media_type(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, dispatcher, _ = route_client

    response = client.post(
        "/api/lectures",
        data={"duration_seconds": "60"},
        files={"file": ("notes.txt", b"not video", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert dispatcher.dispatched == []


def test_create_rejects_upload_over_configured_limit(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, dispatcher, _ = route_client

    response = client.post(
        "/api/lectures",
        data={"duration_seconds": "60"},
        files={"file": ("large.mp4", b"x" * (1024 * 1024 + 1), "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert dispatcher.dispatched == []


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (
            {
                "filename": "notes.txt",
                "content_type": "text/plain",
                "total_size": 10,
                "chunk_size": 4,
            },
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        (
            {
                "filename": "large.mp4",
                "content_type": "video/mp4",
                "total_size": 1024 * 1024 + 1,
                "chunk_size": 1024,
            },
            "UPLOAD_TOO_LARGE",
        ),
    ],
)
def test_chunked_upload_init_validates_type_and_size(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
    payload: dict[str, str | int],
    error_code: str,
) -> None:
    client, dispatcher, _ = route_client

    response = client.post("/api/lectures/uploads", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == error_code
    assert dispatcher.dispatched == []


def start_chunked_upload(client: TestClient) -> dict[str, str | int]:
    response = client.post(
        "/api/lectures/uploads",
        json={
            "filename": "chunked.mp4",
            "content_type": "video/mp4",
            "total_size": 10,
            "chunk_size": 4,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_chunk_upload_writes_numbered_chunk_file(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner], tmp_path: Path
) -> None:
    client, _, _ = route_client
    upload = start_chunked_upload(client)

    response = client.put(
        f"/api/lectures/uploads/{upload['upload_id']}/chunks/1",
        content=b"4567",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 204
    assert (tmp_path / "uploads" / str(upload["upload_id"]) / "1").read_bytes() == b"4567"


def test_chunked_upload_complete_rejects_missing_chunk(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, dispatcher, _ = route_client
    upload = start_chunked_upload(client)
    client.put(
        f"/api/lectures/uploads/{upload['upload_id']}/chunks/0",
        content=b"0123",
        headers={"Content-Type": "application/octet-stream"},
    )

    response = client.post(
        f"/api/lectures/uploads/{upload['upload_id']}/complete",
        json={"title": "Chunked lecture", "duration_seconds": 60},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CHUNK_MISSING"
    assert dispatcher.dispatched == []


def test_chunked_upload_complete_creates_lecture_and_job(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner], tmp_path: Path
) -> None:
    client, dispatcher, _ = route_client
    upload = start_chunked_upload(client)
    assert upload["expected_chunk_count"] == 3
    for index, content in enumerate((b"0123", b"4567", b"89")):
        response = client.put(
            f"/api/lectures/uploads/{upload['upload_id']}/chunks/{index}",
            content=content,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response.status_code == 204

    completed = client.post(
        f"/api/lectures/uploads/{upload['upload_id']}/complete",
        json={"title": "Chunked lecture", "duration_seconds": 60},
    )
    lecture = client.get(f"/api/lectures/{completed.json()['lecture_id']}")

    assert completed.status_code == 202
    assert completed.json()["status"] == "QUEUED"
    assert lecture.status_code == 200
    assert lecture.json()["title"] == "Chunked lecture"
    assert dispatcher.dispatched[0][0] == completed.json()["job_id"]
    assert not (tmp_path / "uploads" / str(upload["upload_id"])).exists()
    media_files = [path for path in tmp_path.glob("*.mp4")]
    assert len(media_files) == 1
    assert media_files[0].read_bytes() == b"0123456789"


def test_chunked_upload_detects_existing_identical_lecture(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner], tmp_path: Path
) -> None:
    client, dispatcher, _ = route_client
    existing = create_lecture(client)
    upload = start_chunked_upload(client)
    for index, content in enumerate((b"0123", b"4567", b"89")):
        assert (
            client.put(
                f"/api/lectures/uploads/{upload['upload_id']}/chunks/{index}",
                content=content,
                headers={"Content-Type": "application/octet-stream"},
            ).status_code
            == 204
        )

    completed = client.post(
        f"/api/lectures/uploads/{upload['upload_id']}/complete",
        json={"title": "Duplicate chunked lecture", "duration_seconds": 60},
    )

    assert completed.status_code == 202
    assert completed.json()["duplicate"] is True
    assert completed.json()["lecture_id"] == existing["lecture_id"]
    assert completed.json()["job_id"] == existing["job_id"]
    assert len(dispatcher.dispatched) == 1
    assert len(list(tmp_path.glob("*.mp4"))) == 1


def test_delete_lecture_removes_rows_and_media_file(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
    route_database: sessionmaker[Session],
) -> None:
    client, _, _ = route_client
    created = create_lecture(client)
    with route_database() as session:
        lecture = session.get(Lecture, created["lecture_id"])
        assert lecture is not None
        media_path = Path(lecture.media_path)
        assert media_path.exists()

    response = client.delete(f"/api/lectures/{created['lecture_id']}")

    assert response.status_code == 204
    assert not media_path.exists()
    with route_database() as session:
        assert session.get(Lecture, created["lecture_id"]) is None
        assert session.get(ProcessingJob, created["job_id"]) is None
    assert client.get(f"/api/lectures/{created['lecture_id']}").status_code == 404


def test_delete_lecture_returns_404_for_non_owner(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, _, _ = route_client
    created = create_lecture(client)
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/signup",
            json={"email": "delete-other@example.com", "password": "test-password"},
        ).status_code
        == 201
    )

    response = client.delete(f"/api/lectures/{created['lecture_id']}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LECTURE_NOT_FOUND"


def test_retry_failed_lecture_resets_and_redispatches_job(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
    route_database: sessionmaker[Session],
) -> None:
    client, dispatcher, _ = route_client
    created = create_lecture(client)
    with route_database() as session:
        job = session.get(ProcessingJob, created["job_id"])
        assert job is not None
        job.mark_failed("TRANSCRIPTION_FAILED", "Provider unavailable")
        job.progress = 55
        session.commit()

    response = client.post(f"/api/lectures/{created['lecture_id']}/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    assert response.json()["job_id"] == created["job_id"]
    with route_database() as session:
        job = session.get(ProcessingJob, created["job_id"])
        assert job is not None
        assert job.status == ProcessingStatus.QUEUED
        assert job.stage == "VALIDATING"
        assert job.progress == 0
        assert job.error_code is None
        assert job.error_message is None
    assert [job_id for job_id, _ in dispatcher.dispatched] == [
        created["job_id"],
        created["job_id"],
    ]


def test_retry_is_rejected_unless_lecture_failed(
    route_client: tuple[TestClient, RecordingDispatcher, VideoLinkSigner],
) -> None:
    client, dispatcher, _ = route_client
    created = create_lecture(client)

    response = client.post(f"/api/lectures/{created['lecture_id']}/retry")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LECTURE_NOT_FAILED"
    assert len(dispatcher.dispatched) == 1
