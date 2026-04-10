from sqlalchemy import Column, String, Text, Float, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
import enum
import uuid

from app.models.database import Base


class DocumentType(str, enum.Enum):
    MARKSHEET_10TH = "MARKSHEET_10TH"
    MARKSHEET_12TH = "MARKSHEET_12TH"
    AADHAR = "AADHAR"


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, nullable=False, index=True)
    doc_type = Column(SAEnum(DocumentType), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False, index=True)
    application_id = Column(String, nullable=False, index=True)
    doc_type = Column(SAEnum(DocumentType), nullable=False)
    extracted_data = Column(Text, nullable=True)   # JSON string
    confidence_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, nullable=False, index=True, unique=True)
    checks = Column(Text, nullable=True)           # JSON string
    overall_score = Column(Float, nullable=True)
    decision = Column(SAEnum(VerificationStatus), default=VerificationStatus.PENDING)
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
