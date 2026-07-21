from io import BytesIO
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.services.media import MediaService
from app.services import media as media_module


def test_upload_uses_server_controlled_filename(tmp_path: Path) -> None:
    service = MediaService(Settings(media_storage_path=tmp_path, max_upload_size_mb=1))
    upload = UploadFile(
        filename="../../unsafe.mp4", file=BytesIO(b"video"), headers={"content-type": "video/mp4"}
    )

    path, size, media_hash = service.save_upload(upload)

    assert path.parent == tmp_path
    assert path.name != "unsafe.mp4"
    assert path.suffix == ".mp4"
    assert size == 5
    assert media_hash == sha256(b"video").hexdigest()


def test_rejects_unsupported_media(tmp_path: Path) -> None:
    service = MediaService(Settings(media_storage_path=tmp_path))
    upload = UploadFile(
        filename="notes.txt", file=BytesIO(b"text"), headers={"content-type": "text/plain"}
    )

    with pytest.raises(ApplicationError, match="MP4") as raised:
        service.save_upload(upload)

    assert raised.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_audio_chunk_plan_uses_ordered_offsets_and_remainder() -> None:
    assert MediaService.plan_audio_chunks(2501, 1000) == [
        (0, 1000),
        (1000, 1000),
        (2000, 501),
    ]
    assert MediaService.plan_audio_chunks(900, 1200) == [(0, 900)]


def test_extract_audio_uses_ffmpeg_segmentation_for_long_lecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = MediaService(
        Settings(_env_file=None, media_storage_path=tmp_path, processing_mode="celery")
    )
    video_path = tmp_path / "lecture.mp4"
    video_path.write_bytes(b"video")
    recorded_command: list[str] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        recorded_command.extend(command)
        output_pattern = Path(command[-1])
        for index in range(3):
            Path(str(output_pattern).replace("%05d", f"{index:05d}")).write_bytes(b"audio")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(media_module.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(media_module.subprocess, "run", fake_run)

    chunks = service.extract_audio(video_path, 2501, chunk_duration_seconds=1000)

    assert "segment" in recorded_command
    assert [(chunk.start_offset_seconds, chunk.duration_seconds) for chunk in chunks] == [
        (0, 1000),
        (1000, 1000),
        (2000, 501),
    ]
    assert all(chunk.path.exists() for chunk in chunks)

    service.cleanup_audio(chunks)

    assert all(not chunk.path.exists() for chunk in chunks)


def test_extract_audio_skips_segmentation_for_short_lecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = MediaService(
        Settings(_env_file=None, media_storage_path=tmp_path, processing_mode="celery")
    )
    video_path = tmp_path / "lecture.mp4"
    video_path.write_bytes(b"video")
    recorded_command: list[str] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        recorded_command.extend(command)
        Path(command[-1]).write_bytes(b"audio")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(media_module.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(media_module.subprocess, "run", fake_run)

    chunks = service.extract_audio(video_path, 900)

    assert "segment" not in recorded_command
    assert len(chunks) == 1
    assert chunks[0].start_offset_seconds == 0
    assert chunks[0].duration_seconds == 900
