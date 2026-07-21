import os
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.services.media import MediaService
from app.services.uploads import ChunkedUploadService, STALE_UPLOAD_SECONDS


def test_cleanup_removes_only_stale_upload_sessions(tmp_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    stale = upload_root / str(uuid4())
    active = upload_root / str(uuid4())
    stale.mkdir(parents=True)
    active.mkdir()
    os.utime(stale, (0, 0))
    now = STALE_UPLOAD_SECONDS + 10
    os.utime(active, (now, now))
    media = MediaService(Settings(_env_file=None, media_storage_path=tmp_path))

    removed = ChunkedUploadService.cleanup_stale(media, now=now)

    assert removed == 1
    assert not stale.exists()
    assert active.exists()
