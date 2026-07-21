import shutil
import subprocess
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.schemas.media import AudioChunk


ALLOWED_MEDIA_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
AUDIO_CHUNK_DURATION_SECONDS = 1200.0


class MediaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def maximum_upload_bytes(self) -> int:
        return self.settings.max_upload_size_mb * 1024 * 1024

    def validate_upload(
        self, filename: str, content_type: str, total_size: int | None = None
    ) -> str:
        suffix = ALLOWED_MEDIA_TYPES.get(content_type)
        uploaded_suffix = Path(filename).suffix.lower()
        if suffix is None or uploaded_suffix != suffix:
            raise ApplicationError("UNSUPPORTED_MEDIA_TYPE", "Upload an MP4, WebM, or MOV video.")
        if total_size is not None and (total_size <= 0 or total_size > self.maximum_upload_bytes):
            raise ApplicationError("UPLOAD_TOO_LARGE", "The uploaded video is too large.")
        return suffix

    def save_upload(self, upload: UploadFile) -> tuple[Path, int, str]:
        suffix = self.validate_upload(upload.filename or "", upload.content_type or "")
        self.settings.media_storage_path.mkdir(parents=True, exist_ok=True)
        destination = self.settings.media_storage_path / f"{uuid4()}{suffix}"
        size = 0
        digest = sha256()
        try:
            with destination.open("wb") as output:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.maximum_upload_bytes:
                        raise ApplicationError(
                            "UPLOAD_TOO_LARGE", "The uploaded video is too large."
                        )
                    output.write(chunk)
                    digest.update(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination, size, digest.hexdigest()

    def inspect_duration(self, path: Path, claimed_duration: float) -> float:
        if (
            claimed_duration <= 0
            or claimed_duration > self.settings.max_video_duration_minutes * 60
        ):
            raise ApplicationError(
                "VIDEO_TOO_LONG", "The video duration is outside the allowed range."
            )
        if self.settings.processing_mode == "mock":
            return claimed_duration
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise ApplicationError(
                "MEDIA_INSPECTION_FAILED", "FFprobe is required to inspect videos."
            )
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise ApplicationError(
                "MEDIA_INSPECTION_FAILED", "The uploaded video could not be inspected."
            )
        duration = float(result.stdout.strip())
        if duration > self.settings.max_video_duration_minutes * 60:
            raise ApplicationError("VIDEO_TOO_LONG", "The video exceeds the maximum duration.")
        return duration

    @staticmethod
    def plan_audio_chunks(
        duration_seconds: float,
        chunk_duration_seconds: float = AUDIO_CHUNK_DURATION_SECONDS,
    ) -> list[tuple[float, float]]:
        if duration_seconds <= 0 or chunk_duration_seconds <= 0:
            raise ValueError("Audio duration and chunk duration must be positive.")
        chunks: list[tuple[float, float]] = []
        offset = 0.0
        while offset < duration_seconds:
            chunk_duration = min(chunk_duration_seconds, duration_seconds - offset)
            chunks.append((offset, chunk_duration))
            offset += chunk_duration_seconds
        return chunks

    def extract_audio(
        self,
        video_path: Path,
        duration_seconds: float,
        chunk_duration_seconds: float = AUDIO_CHUNK_DURATION_SECONDS,
    ) -> list[AudioChunk]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ApplicationError(
                "AUDIO_EXTRACTION_FAILED", "FFmpeg is required to process videos."
            )

        plan = self.plan_audio_chunks(duration_seconds, chunk_duration_seconds)
        audio_directory = self.settings.media_storage_path / "audio" / str(uuid4())
        audio_directory.mkdir(parents=True)
        output_pattern = audio_directory / "chunk-%05d.m4a"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
        ]
        if len(plan) > 1:
            command.extend(
                [
                    "-f",
                    "segment",
                    "-segment_time",
                    str(chunk_duration_seconds),
                    "-reset_timestamps",
                    "1",
                ]
            )
        command.append(
            str(output_pattern if len(plan) > 1 else audio_directory / "chunk-00000.m4a")
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(300, int(duration_seconds)),
                check=False,
            )
            paths = sorted(audio_directory.glob("chunk-*.m4a"))
            if result.returncode != 0 or len(paths) != len(plan):
                raise ApplicationError(
                    "AUDIO_EXTRACTION_FAILED", "The lecture audio could not be extracted."
                )
            return [
                AudioChunk(path=path, start_offset_seconds=offset, duration_seconds=duration)
                for path, (offset, duration) in zip(paths, plan, strict=True)
            ]
        except ApplicationError:
            shutil.rmtree(audio_directory, ignore_errors=True)
            raise
        except (OSError, subprocess.SubprocessError) as error:
            shutil.rmtree(audio_directory, ignore_errors=True)
            raise ApplicationError(
                "AUDIO_EXTRACTION_FAILED", "The lecture audio could not be extracted."
            ) from error

    def cleanup_audio(self, audio_chunks: list[AudioChunk]) -> None:
        temporary_paths = [chunk.path for chunk in audio_chunks if chunk.temporary]
        for path in temporary_paths:
            path.unlink(missing_ok=True)
        for directory in {path.parent for path in temporary_paths}:
            try:
                directory.rmdir()
            except OSError:
                pass
