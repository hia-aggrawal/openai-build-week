from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ComplexityCategory(StrEnum):
    INTRODUCTION = "INTRODUCTION"
    EXAMPLE = "EXAMPLE"
    EXPLANATION = "EXPLANATION"
    DENSE_CONCEPT = "DENSE_CONCEPT"


class TranscriptSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1)


class ComplexityResult(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    complexity_score: int = Field(ge=1, le=5)
    category: ComplexityCategory
    reason: str
    confidence: float = Field(ge=0, le=1)


class PlaybackSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    playback_rate: float = Field(ge=0.25, le=4)
    complexity_score: int = Field(ge=1, le=5)
    category: ComplexityCategory
    reason: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    stage: str
    progress: int
    error_code: str | None
    error_message: str | None


class LectureCreatedResponse(BaseModel):
    lecture_id: str
    job_id: str
    status: str
    duplicate: bool = False


class UploadSessionCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    total_size: int = Field(gt=0)
    chunk_size: int = Field(gt=0)


class UploadSessionCreatedResponse(BaseModel):
    upload_id: str
    expected_chunk_count: int


class UploadCompleteRequest(BaseModel):
    title: str = Field(default="", max_length=255)
    duration_seconds: float = Field(gt=0)


class LectureSummaryResponse(BaseModel):
    id: str
    title: str
    duration_seconds: float
    created_at: datetime
    job_status: str


class LectureListResponse(BaseModel):
    items: list[LectureSummaryResponse]
    limit: int
    offset: int
    next_offset: int | None


class LectureResponse(BaseModel):
    id: str
    title: str
    duration_seconds: float
    video_url: str
    captions_url: str
    job: JobResponse
    transcript: list[TranscriptSegment] | None
    playback_profile: list[PlaybackSegment] | None
