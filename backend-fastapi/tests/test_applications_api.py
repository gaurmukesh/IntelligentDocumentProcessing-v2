"""
Unit tests for Phase 6 — Applications pipeline status endpoint

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_applications_api.py -v
"""

import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.models.database import Base, get_db
from app.models.document import (
    Document, ExtractionResult, ValidationResult,
    DocumentStatus, DocumentType, VerificationStatus,
)

# ── In-memory SQLite for tests ────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def _init_db():
    async with test_engine.begin() as conn:
        from app.models import document  # noqa
        await conn.run_sync(Base.metadata.create_all)


async def _drop_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    asyncio.run(_init_db())
    yield
    asyncio.run(_drop_db())


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


async def _insert(objects: list):
    async with TestSessionLocal() as db:
        for obj in objects:
            db.add(obj)
        await db.commit()


async def _clear_tables():
    async with TestSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text("DELETE FROM validation_results"))
        await db.execute(text("DELETE FROM extraction_results"))
        await db.execute(text("DELETE FROM documents"))
        await db.commit()


@pytest.fixture(autouse=True)
def clean_db():
    asyncio.run(_clear_tables())
    yield


# ── GET /applications/{id}/pipeline-status ───────────────────────

class TestGetPipelineStatus:

    def _doc(self, doc_type, status=DocumentStatus.EXTRACTED, app_id="app-001"):
        return Document(
            application_id=app_id,
            doc_type=doc_type,
            file_name=f"{doc_type}.pdf",
            file_path=f"/tmp/{doc_type}.pdf",
            status=status,
        )

    def _extraction(self, doc_id, doc_type, confidence=0.92, app_id="app-001"):
        return ExtractionResult(
            document_id=doc_id,
            application_id=app_id,
            doc_type=doc_type,
            extracted_data=json.dumps({"test": "data"}),
            confidence_score=confidence,
        )

    def _validation(self, app_id="app-001", decision=VerificationStatus.APPROVED, score=0.90):
        return ValidationResult(
            application_id=app_id,
            checks=json.dumps([{"check_name": "test", "status": "PASS", "detail": "ok"}]),
            overall_score=score,
            decision=decision,
            decision_reason="All checks passed",
        )

    def test_returns_200_and_complete_stage(self, client):
        docs = [
            self._doc(DocumentType.MARKSHEET_10TH),
            self._doc(DocumentType.MARKSHEET_12TH),
            self._doc(DocumentType.AADHAR),
        ]
        asyncio.run(_insert(docs))

        extractions = [
            self._extraction(docs[0].id, DocumentType.MARKSHEET_10TH, 0.95),
            self._extraction(docs[1].id, DocumentType.MARKSHEET_12TH, 0.91),
            self._extraction(docs[2].id, DocumentType.AADHAR, 0.88),
        ]
        validation = self._validation()
        asyncio.run(_insert(extractions + [validation]))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "app-001"
        assert data["pipeline_stage"] == "COMPLETE"
        assert len(data["documents"]) == 3
        assert data["verification"]["decision"] == VerificationStatus.APPROVED

    def test_pipeline_stage_extracting(self, client):
        docs = [
            self._doc(DocumentType.MARKSHEET_10TH, DocumentStatus.EXTRACTING),
            self._doc(DocumentType.MARKSHEET_12TH, DocumentStatus.EXTRACTED),
        ]
        asyncio.run(_insert(docs))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        assert response.json()["pipeline_stage"] == "EXTRACTING"

    def test_pipeline_stage_failed(self, client):
        docs = [
            self._doc(DocumentType.MARKSHEET_10TH, DocumentStatus.FAILED),
            self._doc(DocumentType.MARKSHEET_12TH, DocumentStatus.EXTRACTED),
        ]
        asyncio.run(_insert(docs))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        assert response.json()["pipeline_stage"] == "FAILED"

    def test_pipeline_stage_validating_when_no_validation_result(self, client):
        docs = [self._doc(DocumentType.AADHAR, DocumentStatus.EXTRACTED)]
        asyncio.run(_insert(docs))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        assert response.json()["pipeline_stage"] == "VALIDATING"

    def test_pipeline_stage_uploading_when_pending(self, client):
        docs = [self._doc(DocumentType.AADHAR, DocumentStatus.PENDING)]
        asyncio.run(_insert(docs))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        assert response.json()["pipeline_stage"] == "UPLOADING"

    def test_returns_404_when_no_documents(self, client):
        response = client.get("/applications/app-missing/pipeline-status")
        assert response.status_code == 404

    def test_verification_is_none_before_validation(self, client):
        docs = [self._doc(DocumentType.AADHAR, DocumentStatus.EXTRACTED)]
        asyncio.run(_insert(docs))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        assert response.json()["verification"] is None

    def test_document_summary_includes_confidence(self, client):
        doc = self._doc(DocumentType.MARKSHEET_12TH)
        asyncio.run(_insert([doc]))
        ext = self._extraction(doc.id, DocumentType.MARKSHEET_12TH, 0.88)
        asyncio.run(_insert([ext]))

        response = client.get("/applications/app-001/pipeline-status")

        assert response.status_code == 200
        doc_summary = response.json()["documents"][0]
        assert doc_summary["confidence_score"] == 0.88
        assert doc_summary["doc_type"] == DocumentType.MARKSHEET_12TH


# ── verify.py: ERP callback ───────────────────────────────────────

class TestErpCallback:

    @pytest.mark.asyncio
    @patch("app.routers.verify.httpx.AsyncClient")
    async def test_notify_erp_posts_to_correct_url(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        from app.routers.verify import _notify_erp
        await _notify_erp("app-001", {
            "decision": "APPROVED",
            "overall_score": 0.92,
            "decision_reason": "All checks passed",
        })

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "app-001" in call_url
        assert "verification-result" in call_url

    @pytest.mark.asyncio
    @patch("app.routers.verify.httpx.AsyncClient")
    async def test_notify_erp_does_not_raise_on_connection_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        from app.routers.verify import _notify_erp
        # Should not raise
        await _notify_erp("app-001", {"decision": "APPROVED", "overall_score": 0.9, "decision_reason": ""})

    @pytest.mark.asyncio
    @patch("app.routers.verify.httpx.AsyncClient")
    async def test_notify_erp_does_not_raise_on_500(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        from app.routers.verify import _notify_erp
        # Should not raise even on 500 from Spring Boot
        await _notify_erp("app-001", {"decision": "REJECTED", "overall_score": 0.3, "decision_reason": "DOB mismatch"})
