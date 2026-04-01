"""
Content upload, ingestion, and passage retrieval.
"""

import uuid
from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import InstructorUser
from app.models.content import ContentDocument, ContentPassage
from app.models.course import Course
from app.schemas.content import DocumentOut, PassageOut, IngestionStatus
from app.services.content_ingestion import ContentIngestionService
from app.services.vector_store import VectorStoreService

router = APIRouter(prefix="/api/content", tags=["Content Ingestion"])

ALLOWED_TYPES = {"pdf", "docx", "pptx"}


@router.post("/upload/{course_id}", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    course_id: int,
    file: UploadFile = File(...),
    user: InstructorUser = None,  # type: ignore
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your course")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed. Use: {ALLOWED_TYPES}")

    # Read and save
    content_bytes = await file.read()
    if len(content_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = Path(settings.UPLOAD_DIR) / filename
    save_path.write_bytes(content_bytes)

    doc = ContentDocument(
        course_id=course_id,
        filename=filename,
        original_filename=file.filename or "unknown",
        file_type=ext,
        file_size=len(content_bytes),
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/ingest/{document_id}", response_model=IngestionStatus)
def ingest_document(
    document_id: int,
    user: InstructorUser = None,  # type: ignore
    db: Session = Depends(get_db),
):
    doc = db.query(ContentDocument).filter(ContentDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.upload_status = "processing"
    db.commit()

    try:
        ingestion_svc = ContentIngestionService()
        file_path = Path(settings.UPLOAD_DIR) / doc.filename
        passages_data = ingestion_svc.parse_and_chunk(str(file_path), doc.file_type)

        vs_service = VectorStoreService()
        passage_records: list[ContentPassage] = []

        for idx, pdata in enumerate(passages_data):
            passage = ContentPassage(
                document_id=doc.id,
                content=pdata["text"],
                page_number=pdata.get("page"),
                chunk_index=idx,
            )
            db.add(passage)
            db.flush()

            emb_id = vs_service.add_passage(
                collection_name=f"course_{doc.course_id}",
                passage_id=str(passage.id),
                text=pdata["text"],
                metadata={
                    "document_id": doc.id,
                    "course_id": doc.course_id,
                    "page": pdata.get("page"),
                    "chunk_index": idx,
                },
            )
            passage.embedding_id = emb_id
            passage_records.append(passage)

        doc.upload_status = "indexed"
        db.commit()

        return IngestionStatus(
            document_id=doc.id,
            status="indexed",
            passages_created=len(passage_records),
            message="Content ingested and indexed successfully",
        )
    except Exception as e:
        doc.upload_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/documents/{course_id}", response_model=List[DocumentOut])
def list_documents(course_id: int, user: InstructorUser = None, db: Session = Depends(get_db)):  # type: ignore
    return db.query(ContentDocument).filter(ContentDocument.course_id == course_id).all()


@router.get("/passages/{document_id}", response_model=List[PassageOut])
def list_passages(document_id: int, user: InstructorUser = None, db: Session = Depends(get_db)):  # type: ignore
    return db.query(ContentPassage).filter(ContentPassage.document_id == document_id).all()


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, user: InstructorUser = None, db: Session = Depends(get_db)):  # type: ignore
    doc = db.query(ContentDocument).filter(ContentDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from vector store
    try:
        vs_service = VectorStoreService()
        passage_ids = [str(p.id) for p in doc.passages]
        if passage_ids:
            vs_service.delete_passages(f"course_{doc.course_id}", passage_ids)
    except Exception:
        pass

    # Remove file
    file_path = Path(settings.UPLOAD_DIR) / doc.filename
    if file_path.exists():
        file_path.unlink()

    db.delete(doc)
    db.commit()