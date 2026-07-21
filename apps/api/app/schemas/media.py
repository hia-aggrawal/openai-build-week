from pathlib import Path

from pydantic import BaseModel, Field


class AudioChunk(BaseModel):
    path: Path
    start_offset_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    temporary: bool = True
