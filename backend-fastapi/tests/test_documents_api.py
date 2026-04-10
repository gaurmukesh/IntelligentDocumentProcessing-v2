"""
Unit tests for Phase 2 — Document Upload API

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_documents_api.py -v
"""

import io
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.models.database import Base, get_db
from app.models.document import DocumentType, DocumentStatus
from app.routers.documents import validate_file

# ── In-memory SQLite DB for tests ────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def init_test_db():
    async with test_engine.begin() as conn:
        from app.models import document  # noqa
        await conn.run_sync(Base.metadata.create_all)


async def drop_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(init_test_db())
    yield
    asyncio.run(drop_test_db())


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    # Mock Kafka producer so tests don't need Kafka running
    with patch("app.routers.documents.send_extraction_job", return_value=True):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────

def make_upload_file(content: bytes = b"dummy content", filename: str = "test.pdf",
                     content_type: str = "application/pdf"):
    return ("file", (filename, io.BytesIO(content), content_type))


# ── validate_file() unit tests ────────────────────────────────────

class TestValidateFile:

    def _mock_upload(self, filename: str, content_type: str):
        mock = MagicMock()
        mock.filename = filename
        mock.content_type = content_type
        return mock

    def test_valid_pdf_passes(self):
        from fastapi import HTTPException
        file = self._mock_upload("doc.pdf", "application/pdf")
        validate_file(file)   # should not raise

    def test_valid_jpg_passes(self):
        file = self._mock_upload("doc.jpg", "image/jpeg")
        validate_file(file)

    def test_valid_png_passes(self):
        file = self._mock_upload("doc.png", "image/png")
        validate_file(file)

    def test_invalid_extension_raises(self):
        from fastapi import HTTPException
        file = self._mock_upload("doc.docx", "application/pdf")
        with pytest.raises(HTTPException) as exc:
            validate_file(file)
        assert exc.value.status_code == 400
        assert "Unsupported file type" in exc.value.detail

    def test_invalid_content_type_raises(self):
        from fastapi import HTTPException
        file = self._mock_upload("doc.pdf", "text/plain")
        with pytest.raises(HTTPException) as exc:
            validate_file(file)
        assert exc.value.status_code == 400

    def test_exe_extension_raises(self):
        from fastapi import HTTPException
        file = self._mock_upload("virus.exe", "application/octet-stream")
        with pytest.raises(HTTPException) as exc:
            validate_file(file)
        assert exc.value.status_code == 400


# ── Upload endpoint tests ─────────────────────────────────────────

class TestUploadEndpoint:

    def test_upload_pdf_success(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-001", "doc_type": "MARKSHEET_10TH"},
                files=[make_upload_file(b"pdf content", "marksheet.pdf", "application/pdf")],
            )
        assert response.status_code == 200
        body = response.json()
        assert body["application_id"] == "APP-001"
        assert body["doc_type"] == "MARKSHEET_10TH"
        assert body["status"] == "PENDING"
        assert "id" in body

    def test_upload_jpg_success(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-002", "doc_type": "AADHAR"},
                files=[make_upload_file(b"image data", "aadhar.jpg", "image/jpeg")],
            )
        assert response.status_code == 200
        assert response.json()["doc_type"] == "AADHAR"

    def test_upload_png_success(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-003", "doc_type": "MARKSHEET_12TH"},
                files=[make_upload_file(b"image data", "marksheet.png", "image/png")],
            )
        assert response.status_code == 200

    def test_upload_invalid_extension_returns_400(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-004", "doc_type": "AADHAR"},
                files=[make_upload_file(b"data", "aadhar.docx", "application/pdf")],
            )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_invalid_doc_type_returns_422(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-005", "doc_type": "INVALID_TYPE"},
                files=[make_upload_file(b"data", "doc.pdf", "application/pdf")],
            )
        assert response.status_code == 422

    def test_upload_oversized_file_returns_400(self, client, tmp_path):
        large_content = b"x" * (11 * 1024 * 1024)   # 11MB — exceeds 10MB limit
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"application_id": "APP-006", "doc_type": "MARKSHEET_10TH"},
                files=[make_upload_file(large_content, "big.pdf", "application/pdf")],
            )
        assert response.status_code == 400
        assert "exceeds limit" in response.json()["detail"]

    def test_upload_missing_application_id_returns_422(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            response = client.post(
                "/documents/upload",
                data={"doc_type": "AADHAR"},
                files=[make_upload_file(b"data", "doc.pdf", "application/pdf")],
            )
        assert response.status_code == 422

    def test_upload_file_saved_to_disk(self, client, tmp_path):
        with patch("app.routers.documents.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            client.post(
                "/documents/upload",
                data={"application_id": "APP-DISK-TEST", "doc_type": "AADHAR"},
                files=[make_upload_file(b"file content", "aadhar.pdf", "application/pdf")],
            )
        saved_files = list((tmp_path / "APP-DISK-TEST").glob("*.pdf"))
        assert len(saved_files) == 1

    def test_kafka_producer_called_on_upload(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            with patch("app.routers.documents.send_extraction_job", return_value=True) as mock_kafka:
                client.post(
                    "/documents/upload",
                    data={"application_id": "APP-KAFKA-TEST", "doc_type": "MARKSHEET_10TH"},
                    files=[make_upload_file(b"data", "doc.pdf", "application/pdf")],
                )
                mock_kafka.assert_called_once()


# ── Get documents endpoint tests ──────────────────────────────────

class TestGetDocumentsEndpoint:

    def test_get_documents_returns_list(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            # Upload a document first
            client.post(
                "/documents/upload",
                data={"application_id": "APP-GET-001", "doc_type": "MARKSHEET_10TH"},
                files=[make_upload_file(b"data", "doc.pdf", "application/pdf")],
            )
            response = client.get("/documents/APP-GET-001")
        assert response.status_code == 200
        docs = response.json()
        assert isinstance(docs, list)
        assert len(docs) == 1
        assert docs[0]["application_id"] == "APP-GET-001"

    def test_get_documents_empty_for_unknown_application(self, client):
        response = client.get("/documents/NON-EXISTENT-APP")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_documents_returns_correct_doc_type(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            client.post(
                "/documents/upload",
                data={"application_id": "APP-GET-002", "doc_type": "AADHAR"},
                files=[make_upload_file(b"data", "aadhar.jpg", "image/jpeg")],
            )
            response = client.get("/documents/APP-GET-002")
        docs = response.json()
        assert docs[0]["doc_type"] == "AADHAR"

    def test_get_documents_multiple_uploads(self, client, tmp_path):
        with patch("app.core.config.settings.upload_dir", str(tmp_path)):
            for doc_type, filename in [
                ("MARKSHEET_10TH", "10th.pdf"),
                ("MARKSHEET_12TH", "12th.pdf"),
                ("AADHAR", "aadhar.jpg"),
            ]:
                mime = "image/jpeg" if filename.endswith(".jpg") else "application/pdf"
                client.post(
                    "/documents/upload",
                    data={"application_id": "APP-MULTI", "doc_type": doc_type},
                    files=[make_upload_file(b"data", filename, mime)],
                )
            response = client.get("/documents/APP-MULTI")
        assert len(response.json()) == 3


# ── Health check ──────────────────────────────────────────────────

class TestHealthCheck:

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "IDP AI Service"
