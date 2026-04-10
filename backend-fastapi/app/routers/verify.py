import json
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.database import get_db, AsyncSessionLocal
from app.models.document import (
    Document, DocumentType, DocumentStatus,
    ExtractionResult, ValidationResult, VerificationStatus
)
from app.models.schemas import ValidationResultResponse, ValidationCheck, VerificationReport
from app.services.validator import run_validation
from app.services.rag import check_eligibility, ingest_knowledge_base, is_knowledge_base_populated

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_validation_task(application_id: str):
    """Background task: validate all extracted docs for an application."""
    async with AsyncSessionLocal() as db:

        # Fetch all extraction results for this application
        result = await db.execute(
            select(ExtractionResult).where(ExtractionResult.application_id == application_id)
        )
        extraction_rows = result.scalars().all()

        if not extraction_rows:
            return

        # Check all documents are extracted
        doc_result = await db.execute(
            select(Document).where(Document.application_id == application_id)
        )
        docs = doc_result.scalars().all()
        pending = [d for d in docs if d.status not in (DocumentStatus.EXTRACTED, DocumentStatus.FAILED)]
        if pending:
            return  # Not all documents processed yet

        # Build extractions dict
        extractions = {}
        doc_confidences = {}
        for row in extraction_rows:
            if row.extracted_data:
                extractions[row.doc_type] = json.loads(row.extracted_data)
                doc_confidences[row.doc_type] = row.confidence_score or 0.0

        if not extractions:
            # All docs failed extraction — save a REJECTED validation result
            logger.error(
                f"No extracted data available for application {application_id} — "
                "all documents may have failed extraction."
            )
            failed_result = ValidationResult(
                application_id=application_id,
                checks=json.dumps([{
                    "check_name": "extraction_check",
                    "status": "FAIL",
                    "detail": "No documents were successfully extracted.",
                }]),
                overall_score=0.0,
                decision=VerificationStatus.REJECTED,
                decision_reason="All document extractions failed — no data to validate.",
            )
            db.add(failed_result)
            await db.commit()
            return

        # Run validation
        validation_output = run_validation(extractions, doc_confidences)

        # Run RAG eligibility check if knowledge base is populated
        rag_check = None
        if is_knowledge_base_populated():
            try:
                # Extract student profile from 12th marksheet
                data_12th = extractions.get(DocumentType.MARKSHEET_12TH, {})
                data_10th = extractions.get(DocumentType.MARKSHEET_10TH, {})

                def _val(field_data):
                    if isinstance(field_data, dict):
                        return field_data.get("value")
                    return field_data

                pct_12th_raw = _val(data_12th.get("percentage", {}))
                pct_10th_raw = _val(data_10th.get("percentage", {}))
                stream = _val(data_12th.get("stream", {}))
                result_12th = _val(data_12th.get("result", {}))

                pct_12th = float(str(pct_12th_raw).replace("%", "")) if pct_12th_raw else None
                pct_10th = float(str(pct_10th_raw).replace("%", "")) if pct_10th_raw else None

                rag_check = check_eligibility(
                    course="General Admission",   # will be enriched from ERP in Phase 6
                    pct_10th=pct_10th,
                    pct_12th=pct_12th,
                    stream=stream,
                    result_12th=result_12th,
                )

                # Add RAG result as a validation check
                rag_status = "PASS" if rag_check.get("eligible") else (
                    "FAIL" if rag_check.get("eligible") is False else "WARNING"
                )
                validation_output["checks"].append({
                    "check_name": "rag_eligibility_check",
                    "status": rag_status,
                    "detail": rag_check.get("reason", "RAG eligibility check"),
                    "confidence": rag_check.get("confidence"),
                })
                logger.info(f"RAG eligibility result for {application_id}: {rag_status}")
            except Exception as e:
                logger.warning(f"RAG eligibility check skipped: {e}")

        # Save or update ValidationResult
        existing = await db.execute(
            select(ValidationResult).where(ValidationResult.application_id == application_id)
        )
        val_result = existing.scalar_one_or_none()

        if val_result:
            val_result.checks = json.dumps(validation_output["checks"])
            val_result.overall_score = validation_output["overall_score"]
            val_result.decision = validation_output["decision"]
            val_result.decision_reason = validation_output["decision_reason"]
        else:
            val_result = ValidationResult(
                application_id=application_id,
                checks=json.dumps(validation_output["checks"]),
                overall_score=validation_output["overall_score"],
                decision=validation_output["decision"],
                decision_reason=validation_output["decision_reason"],
            )
            db.add(val_result)

        await db.commit()

        # Notify Spring Boot ERP with the verification result
        await _notify_erp(application_id, validation_output)


async def _notify_erp(application_id: str, validation_output: dict):
    """POST verification result back to Spring Boot ERP (best-effort)."""
    url = f"{settings.erp_base_url}/api/applications/{application_id}/verification-result"
    payload = {
        "decision": validation_output["decision"],
        "overall_score": validation_output["overall_score"],
        "decision_reason": validation_output["decision_reason"],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code not in (200, 204):
                logger.warning(
                    f"ERP callback returned {response.status_code} for application {application_id}"
                )
            else:
                logger.info(f"ERP notified for application {application_id}: {payload['decision']}")
    except Exception as e:
        logger.warning(f"ERP callback failed for {application_id}: {e}")


# Fixed-path routes MUST come before parameterised routes to avoid shadowing.

@router.post("/knowledge-base/ingest")
async def ingest_knowledge_base_endpoint(background_tasks: BackgroundTasks):
    """Ingest knowledge base documents into the vector store."""
    def _ingest():
        count = ingest_knowledge_base()
        logger.info(f"Knowledge base ingestion complete: {count} chunks")

    background_tasks.add_task(_ingest)
    return {"message": "Knowledge base ingestion started in background"}


@router.get("/knowledge-base/status")
async def knowledge_base_status():
    """Check if the knowledge base has been populated."""
    populated = is_knowledge_base_populated()
    return {"populated": populated, "collection": "idp_knowledge_base"}


@router.post("/{application_id}")
async def trigger_verification(
    application_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger validation for all extracted documents of an application."""
    result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    docs = result.scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail=f"No documents found for application {application_id}")

    background_tasks.add_task(_run_validation_task, application_id)
    return {"message": f"Validation triggered for application {application_id}", "application_id": application_id}


@router.get("/{application_id}/status")
async def get_verification_status(application_id: str, db: AsyncSession = Depends(get_db)):
    """Get current verification status per document."""
    result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    docs = result.scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail=f"No documents found for application {application_id}")

    return {
        "application_id": application_id,
        "documents": [
            {"id": d.id, "doc_type": d.doc_type, "status": d.status}
            for d in docs
        ]
    }


@router.get("/{application_id}/report", response_model=VerificationReport)
async def get_verification_report(application_id: str, db: AsyncSession = Depends(get_db)):
    """Get full verification report for an application."""

    # Validation result
    val_result = await db.execute(
        select(ValidationResult).where(ValidationResult.application_id == application_id)
    )
    val = val_result.scalar_one_or_none()
    if not val:
        raise HTTPException(status_code=404, detail="Verification report not available yet")

    # Extraction results
    ext_result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.application_id == application_id)
    )
    extractions = ext_result.scalars().all()

    from app.models.schemas import ExtractionResultResponse
    extraction_responses = [
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

    checks = [ValidationCheck(**c) for c in json.loads(val.checks)] if val.checks else []

    validation_response = ValidationResultResponse(
        id=val.id,
        application_id=val.application_id,
        checks=checks,
        overall_score=val.overall_score,
        decision=val.decision,
        decision_reason=val.decision_reason,
        created_at=val.created_at,
    )

    return VerificationReport(
        application_id=application_id,
        status=val.decision,
        overall_score=val.overall_score,
        decision_reason=val.decision_reason,
        documents=extraction_responses,
        validation=validation_response,
    )
