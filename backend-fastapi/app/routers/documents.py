from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import uuid
import json

from app.models.database import get_db, AsyncSessionLocal
from app.models.document import Document, DocumentType, DocumentStatus, ExtractionResult
from app.models.schemas import DocumentUploadResponse, DocumentResponse, ExtractionResultResponse
from app.core.config import settings
from app.services.kafka_producer import send_extraction_job
from app.services.storage import upload_file

router = APIRouter()

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_MB = 10


def validate_file(file: UploadFile):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: PDF, JPG, PNG"
        )
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{file.content_type}'"
        )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    application_id: str = Form(...),
    doc_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    validate_file(file)

    # Read file and check size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File size {size_mb:.1f}MB exceeds limit of {MAX_FILE_SIZE_MB}MB"
        )

    # Save to storage (local disk in dev, Lightsail Object Storage in production)
    ext = Path(file.filename).suffix.lower()
    file_name = f"{doc_type.value}_{uuid.uuid4().hex[:8]}{ext}"
    storage_key = f"{application_id}/{file_name}"
    file_ref = upload_file(contents, storage_key)

    # Save document record to DB
    doc = Document(
        application_id=application_id,
        doc_type=doc_type,
        file_name=file_name,
        file_path=file_ref,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Publish extraction job to Kafka
    sent = send_extraction_job(
        document_id=doc.id,
        application_id=application_id,
        doc_type=doc_type.value,
        file_path=str(file_path),
    )
    if not sent:
        # Kafka unavailable — log warning but don't fail the upload
        import logging
        logging.getLogger(__name__).warning(
            f"Kafka unavailable — extraction job not queued for document {doc.id}. "
            f"Start the consumer and re-trigger manually."
        )

    return DocumentUploadResponse(
        id=doc.id,
        application_id=doc.application_id,
        doc_type=doc.doc_type,
        file_name=doc.file_name,
        status=doc.status,
        created_at=doc.created_at,
    )


@router.get("/{application_id}", response_model=list[DocumentResponse])
async def get_documents(application_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=d.id,
            application_id=d.application_id,
            doc_type=d.doc_type,
            file_name=d.file_name,
            status=d.status,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.get("/{application_id}/extraction", response_model=list[ExtractionResultResponse])
async def get_extraction_results(application_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.application_id == application_id)
    )
    extractions = result.scalars().all()
    return [
        ExtractionResultResponse(
            id=e.id,
            document_id=e.document_id,
            application_id=e.application_id,
            doc_type=e.doc_type,
            extracted_data=json.loads(e.extracted_data) if e.extracted_data else None,
            confidence_score=e.confidence_score,
            error_message=e.error_message,
            created_at=e.created_at,
        )
        for e in extractions
    ]
