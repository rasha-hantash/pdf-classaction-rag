from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class IngestedDocument(BaseModel):
    id: UUID
    file_hash: str
    file_path: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ChunkRecord(BaseModel):
    id: UUID | None = None
    document_id: UUID
    content: str
    chunk_type: str | None = None
    page_number: int | None = None
    position: int | None = None
    embedding: list[float] | None = None
    bbox: list[float] | None = None  # [x0, y0, x1, y1] coordinates
    created_at: datetime | None = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and len(v) != 4:
            raise ValueError("bbox must contain exactly 4 coordinates [x0, y0, x1, y1]")
        return v


class SearchResult(BaseModel):
    chunk: ChunkRecord
    score: float
    document: IngestedDocument | None = None
