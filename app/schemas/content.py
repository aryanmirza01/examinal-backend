from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    course_id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    upload_status: str
    uploaded_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PassageOut(BaseModel):
    id: int
    document_id: int
    content: str
    page_number: Optional[int]
    chunk_index: int
    embedding_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionStatus(BaseModel):
    document_id: int
    status: str
    passages_created: int
    message: str