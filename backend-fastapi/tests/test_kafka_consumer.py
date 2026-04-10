"""
Unit tests for Phase 3 — Kafka Consumer (process_message)

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_kafka_consumer.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.document import DocumentStatus, DocumentType


# ── Helpers ───────────────────────────────────────────────────────

def _make_message(doc_id="doc-001", app_id="app-001",
                  doc_type=DocumentType.MARKSHEET_12TH,
                  file_path="/tmp/test.pdf"):
    return {
        "document_id": doc_id,
        "application_id": app_id,
        "doc_type": doc_type.value,
        "file_path": file_path,
    }


def _make_db_session(doc=None):
    """Return an async DB session mock with the document pre-loaded."""
    session = MagicMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = doc

    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── process_message — success ─────────────────────────────────────

class TestProcessMessageSuccess:

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_marks_document_extracted_on_success(self, mock_extract, mock_session_cls):
        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.PENDING

        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.return_value = ({"student_name": {"value": "Rahul", "confidence": 0.95}}, 0.92)

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        assert mock_doc.status == DocumentStatus.EXTRACTED

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_saves_extraction_result_on_success(self, mock_extract, mock_session_cls):
        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.PENDING

        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session

        extracted = {"percentage": {"value": "82.5", "confidence": 0.91}}
        mock_extract.return_value = (extracted, 0.91)

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        session.add.assert_called_once()
        saved = session.add.call_args[0][0]
        assert saved.confidence_score == 0.91
        assert json.loads(saved.extracted_data) == extracted

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_commits_twice_on_success(self, mock_extract, mock_session_cls):
        """Commit once after EXTRACTING status, once after saving result."""
        mock_doc = MagicMock()
        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.return_value = ({}, 0.85)

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        assert session.commit.call_count == 2

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_sets_extracting_status_before_calling_extractor(
        self, mock_extract, mock_session_cls
    ):
        """Document must be EXTRACTING while the API call is in progress."""
        status_during_extract = []

        def capture_status(file_path, doc_type):
            status_during_extract.append(mock_doc.status)
            return ({}, 0.9)

        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.PENDING
        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.side_effect = capture_status

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        assert DocumentStatus.EXTRACTING in status_during_extract


# ── process_message — failure ─────────────────────────────────────

class TestProcessMessageFailure:

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_marks_document_failed_when_extractor_raises(
        self, mock_extract, mock_session_cls
    ):
        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.PENDING

        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.side_effect = Exception("OpenAI API error")

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        assert mock_doc.status == DocumentStatus.FAILED

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_saves_error_message_on_failure(self, mock_extract, mock_session_cls):
        mock_doc = MagicMock()
        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.side_effect = Exception("Rate limit exceeded")

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        session.add.assert_called_once()
        saved = session.add.call_args[0][0]
        assert "Rate limit exceeded" in saved.error_message
        assert saved.confidence_score is None

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_still_commits_after_failure(self, mock_extract, mock_session_cls):
        """Even on failure the FAILED status and error record must be persisted."""
        mock_doc = MagicMock()
        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.side_effect = Exception("Timeout")

        from app.services.kafka_consumer import process_message
        await process_message(_make_message())

        assert session.commit.call_count == 2

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_skips_when_document_not_found(self, mock_extract, mock_session_cls):
        """If document_id is missing from DB, process_message should return early."""
        session = _make_db_session(doc=None)   # document not found
        mock_session_cls.return_value = session

        from app.services.kafka_consumer import process_message
        await process_message(_make_message(doc_id="missing-id"))

        mock_extract.assert_not_called()
        session.add.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.models.database.AsyncSessionLocal")
    @patch("app.services.extractor.extract_document")
    async def test_records_correct_doc_type(self, mock_extract, mock_session_cls):
        mock_doc = MagicMock()
        session = _make_db_session(mock_doc)
        mock_session_cls.return_value = session
        mock_extract.return_value = ({}, 0.88)

        from app.services.kafka_consumer import process_message
        await process_message(_make_message(doc_type=DocumentType.AADHAR))

        saved = session.add.call_args[0][0]
        assert saved.doc_type == DocumentType.AADHAR
