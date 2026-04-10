from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.document import DocumentType, DocumentStatus, VerificationStatus


# ── Document schemas ──────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    id: str
    application_id: str
    doc_type: DocumentType
    file_name: str
    status: DocumentStatus
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    application_id: str
    doc_type: DocumentType
    file_name: str
    status: DocumentStatus
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Extraction result schemas ─────────────────────────────────────

class ExtractionResultResponse(BaseModel):
    id: str
    document_id: str
    application_id: str
    doc_type: DocumentType
    extracted_data: Optional[Dict[str, Any]] = None   # parsed from JSON
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Validation result schemas ─────────────────────────────────────

class ValidationCheck(BaseModel):
    check_name: str
    status: str          # PASS / FAIL / WARNING
    detail: str
    confidence: Optional[float] = None


class ValidationResultResponse(BaseModel):
    id: str
    application_id: str
    checks: Optional[list[ValidationCheck]] = None
    overall_score: Optional[float] = None
    decision: VerificationStatus
    decision_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Verification report schema (full report returned to Spring Boot) ──

class VerificationReport(BaseModel):
    application_id: str
    status: VerificationStatus
    overall_score: Optional[float] = None
    decision_reason: Optional[str] = None
    documents: Optional[list[ExtractionResultResponse]] = None
    validation: Optional[ValidationResultResponse] = None


# ── Error response ────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
