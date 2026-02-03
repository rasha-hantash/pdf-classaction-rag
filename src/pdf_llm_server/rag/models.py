from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    created_at: datetime | None = None


class SearchResult(BaseModel):
    chunk: ChunkRecord
    score: float
    document: IngestedDocument | None = None
