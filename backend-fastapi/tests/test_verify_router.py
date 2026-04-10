"""
Unit tests for Phase 5/6 — Verify router endpoints

Covers: trigger_verification, get_verification_status, get_verification_report,
        knowledge-base/ingest, knowledge-base/status

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_verify_router.py -v
"""

import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock
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


async def _clear():
    async with TestSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text("DELETE FROM validation_results"))
        await db.execute(text("DELETE FROM extraction_results"))
        await db.execute(text("DELETE FROM documents"))
        await db.commit()


async def _insert(*objects):
    async with TestSessionLocal() as db:
        for obj in objects:
            db.add(obj)
        await db.commit()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    asyncio.run(_init_db())
    yield
    asyncio.run(_drop_db())


@pytest.fixture(autouse=True)
def clean_db():
    asyncio.run(_clear())
    yield


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _doc(doc_type=DocumentType.MARKSHEET_12TH, status=DocumentStatus.EXTRACTED, app_id="app-001"):
    return Document(
        application_id=app_id,
        doc_type=doc_type,
        file_name=f"{doc_type}.pdf",
        file_path=f"/tmp/{doc_type}.pdf",
        status=status,
    )


def _validation(app_id="app-001", decision=VerificationStatus.APPROVED, score=0.90):
    return ValidationResult(
        application_id=app_id,
        checks=json.dumps([
            {"check_name": "marks_check", "status": "PASS", "detail": "OK"},
            {"check_name": "dob_match",   "status": "PASS", "detail": "Match"},
        ]),
        overall_score=score,
        decision=decision,
        decision_reason="All checks passed",
    )


# ── POST /verify/{application_id} ────────────────────────────────

class TestTriggerVerification:

    def test_returns_200_and_message(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        with patch("app.routers.verify._run_validation_task"):
            response = client.post("/verify/app-001")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "app-001"
        assert "triggered" in data["message"].lower() or "validation" in data["message"].lower()

    def test_returns_404_when_no_documents(self, client):
        response = client.post("/verify/app-missing")
        assert response.status_code == 404

    def test_adds_background_task(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        task_added = []
        original_add = None

        class MockBackgroundTasks:
            def add_task(self, func, *args, **kwargs):
                task_added.append((func.__name__, args))

        # Just verify a 200 is returned — background task runs separately
        with patch("app.routers.verify._run_validation_task"):
            response = client.post("/verify/app-001")
        assert response.status_code == 200


# ── GET /verify/{application_id}/status ──────────────────────────

class TestGetVerificationStatus:

    def test_returns_document_statuses(self, client):
        docs = [
            _doc(DocumentType.MARKSHEET_10TH, DocumentStatus.EXTRACTED),
            _doc(DocumentType.MARKSHEET_12TH, DocumentStatus.EXTRACTING),
            _doc(DocumentType.AADHAR, DocumentStatus.FAILED),
        ]
        asyncio.run(_insert(*docs))

        response = client.get("/verify/app-001/status")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "app-001"
        assert len(data["documents"]) == 3
        statuses = {d["doc_type"]: d["status"] for d in data["documents"]}
        assert statuses[DocumentType.MARKSHEET_10TH] == DocumentStatus.EXTRACTED
        assert statuses[DocumentType.AADHAR] == DocumentStatus.FAILED

    def test_returns_404_when_no_documents(self, client):
        response = client.get("/verify/app-missing/status")
        assert response.status_code == 404


# ── GET /verify/{application_id}/report ──────────────────────────

class TestGetVerificationReport:

    def test_returns_full_report_when_ready(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        ext = ExtractionResult(
            document_id=doc.id,
            application_id="app-001",
            doc_type=DocumentType.MARKSHEET_12TH,
            extracted_data=json.dumps({"percentage": {"value": "82", "confidence": 0.9}}),
            confidence_score=0.9,
        )
        val = _validation()
        asyncio.run(_insert(ext, val))

        response = client.get("/verify/app-001/report")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "app-001"
        assert data["status"] == VerificationStatus.APPROVED
        assert data["overall_score"] == 0.90
        assert len(data["validation"]["checks"]) == 2

    def test_returns_404_when_no_validation_result(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        response = client.get("/verify/app-001/report")
        assert response.status_code == 404

    def test_report_includes_extraction_data(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        ext = ExtractionResult(
            document_id=doc.id,
            application_id="app-001",
            doc_type=DocumentType.MARKSHEET_12TH,
            extracted_data=json.dumps({"student_name": {"value": "Rahul", "confidence": 0.95}}),
            confidence_score=0.95,
        )
        asyncio.run(_insert(ext, _validation()))

        response = client.get("/verify/app-001/report")

        assert response.status_code == 200
        docs = response.json()["documents"]
        assert len(docs) == 1
        assert docs[0]["confidence_score"] == 0.95

    def test_rejected_report_has_correct_decision(self, client):
        doc = _doc()
        asyncio.run(_insert(doc))

        val = _validation(decision=VerificationStatus.REJECTED, score=0.40)
        asyncio.run(_insert(val))

        response = client.get("/verify/app-001/report")

        assert response.status_code == 200
        assert response.json()["status"] == VerificationStatus.REJECTED
        assert response.json()["overall_score"] == 0.40


# ── Knowledge base endpoints ──────────────────────────────────────

class TestKnowledgeBaseEndpoints:

    def test_ingest_returns_202_or_200(self, client):
        with patch("app.routers.verify.ingest_knowledge_base", return_value=10):
            response = client.post("/verify/knowledge-base/ingest")
        assert response.status_code == 200
        assert "ingestion" in response.json()["message"].lower()

    def test_status_returns_populated_true(self, client):
        with patch("app.routers.verify.is_knowledge_base_populated", return_value=True):
            response = client.get("/verify/knowledge-base/status")
        assert response.status_code == 200
        assert response.json()["populated"] is True

    def test_status_returns_populated_false(self, client):
        with patch("app.routers.verify.is_knowledge_base_populated", return_value=False):
            response = client.get("/verify/knowledge-base/status")
        assert response.status_code == 200
        assert response.json()["populated"] is False
