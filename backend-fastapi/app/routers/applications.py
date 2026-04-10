"""
Application pipeline status — Phase 6

GET /applications/{application_id}/pipeline-status
Returns aggregated pipeline state: documents, extraction, validation.
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.document import Document, ExtractionResult, ValidationResult, DocumentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{application_id}/pipeline-status")
async def get_pipeline_status(application_id: str, db: AsyncSession = Depends(get_db)):
    """
    Aggregated pipeline status for an application.

    Returns:
        - per-document upload + extraction status
        - overall pipeline stage (UPLOADING / EXTRACTING / VALIDATING / COMPLETE / FAILED)
        - verification decision if available
    """
    # Documents
    doc_result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    docs = doc_result.scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail=f"No documents found for application {application_id}")

    # Extraction results
    ext_result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.application_id == application_id)
    )
    extractions = {e.doc_type: e for e in ext_result.scalars().all()}

    # Validation result
    val_result = await db.execute(
        select(ValidationResult).where(ValidationResult.application_id == application_id)
    )
    validation = val_result.scalar_one_or_none()

    # Build per-document summary
    doc_summaries = []
    for doc in docs:
        ext = extractions.get(doc.doc_type)
        doc_summaries.append({
            "id": doc.id,
            "doc_type": doc.doc_type,
            "upload_status": doc.status,
            "confidence_score": ext.confidence_score if ext else None,
            "extraction_error": ext.error_message if ext else None,
        })

    # Derive overall pipeline stage
    statuses = {d.status for d in docs}
    if DocumentStatus.FAILED in statuses:
        pipeline_stage = "FAILED"
    elif any(d.status == DocumentStatus.EXTRACTING for d in docs):
        pipeline_stage = "EXTRACTING"
    elif any(d.status == DocumentStatus.PENDING for d in docs):
        pipeline_stage = "UPLOADING"
    elif validation:
        pipeline_stage = "COMPLETE"
    else:
        pipeline_stage = "VALIDATING"

    return {
        "application_id": application_id,
        "pipeline_stage": pipeline_stage,
        "documents": doc_summaries,
        "verification": {
            "decision": validation.decision if validation else None,
            "overall_score": validation.overall_score if validation else None,
            "decision_reason": validation.decision_reason if validation else None,
        } if validation else None,
    }
