"""
Unit tests for the RAG Knowledge Base Service (Phase 5)

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_rag.py -v
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, mock_open


# ── Helpers ───────────────────────────────────────────────────────

def _make_langchain_doc(content: str, source: str = "test.txt"):
    """Create a minimal LangChain Document-like object."""
    doc = MagicMock()
    doc.page_content = content
    doc.metadata = {"source": source, "topic": source.replace(".txt", "")}
    return doc


# ── ingest_knowledge_base ─────────────────────────────────────────

class TestIngestKnowledgeBase:

    @patch("app.services.rag._get_vector_store")
    def test_returns_zero_when_directory_missing(self, mock_vs):
        from app.services.rag import ingest_knowledge_base
        result = ingest_knowledge_base("/nonexistent/path/xyz")
        assert result == 0
        mock_vs.assert_not_called()

    @patch("app.services.rag._get_vector_store")
    def test_returns_zero_when_no_txt_files(self, mock_vs, tmp_path):
        # Create an empty directory with no .txt files
        (tmp_path / "dummy.pdf").write_text("not a text file")
        from app.services.rag import ingest_knowledge_base
        result = ingest_knowledge_base(str(tmp_path))
        assert result == 0
        mock_vs.assert_not_called()

    @patch("app.services.rag._get_vector_store")
    def test_ingests_txt_files_and_returns_chunk_count(self, mock_vs, tmp_path):
        # Create two .txt files
        (tmp_path / "rules.txt").write_text(
            "Eligibility rule 1: minimum 45% in 12th.\n\nEligibility rule 2: minimum 35% in 10th."
        )
        (tmp_path / "faq.txt").write_text(
            "Q: What is the minimum percentage?\nA: 45% for B.Tech."
        )

        mock_store = MagicMock()
        mock_vs.return_value = mock_store

        from app.services.rag import ingest_knowledge_base
        result = ingest_knowledge_base(str(tmp_path))

        assert result > 0
        mock_store.add_documents.assert_called_once()
        # Verify chunks were passed (not raw docs)
        chunks_passed = mock_store.add_documents.call_args[0][0]
        assert len(chunks_passed) == result

    @patch("app.services.rag._get_vector_store")
    def test_ingests_single_file_correctly(self, mock_vs, tmp_path):
        content = "Minimum 10th percentage: 35%.\nMinimum 12th percentage: 45%."
        (tmp_path / "eligibility.txt").write_text(content)

        mock_store = MagicMock()
        mock_vs.return_value = mock_store

        from app.services.rag import ingest_knowledge_base
        result = ingest_knowledge_base(str(tmp_path))

        assert result >= 1
        mock_store.add_documents.assert_called_once()

    @patch("app.services.rag._get_vector_store")
    def test_chunk_metadata_contains_source_and_topic(self, mock_vs, tmp_path):
        (tmp_path / "board_formats.txt").write_text(
            "CBSE board format.\nRoll number: 8-digit numeric."
        )

        captured_chunks = []

        def capture_add(chunks):
            captured_chunks.extend(chunks)

        mock_store = MagicMock()
        mock_store.add_documents.side_effect = capture_add
        mock_vs.return_value = mock_store

        from app.services.rag import ingest_knowledge_base
        ingest_knowledge_base(str(tmp_path))

        assert len(captured_chunks) >= 1
        assert captured_chunks[0].metadata["source"] == "board_formats.txt"
        assert captured_chunks[0].metadata["topic"] == "board_formats"


# ── is_knowledge_base_populated ───────────────────────────────────

class TestIsKnowledgeBasePopulated:

    @patch("app.services.rag._get_qdrant_client")
    def test_returns_false_when_collection_missing(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get_collections.return_value.collections = []
        mock_client_fn.return_value = mock_client

        from app.services.rag import is_knowledge_base_populated
        assert is_knowledge_base_populated() is False

    @patch("app.services.rag._get_qdrant_client")
    def test_returns_false_when_collection_empty(self, mock_client_fn):
        mock_client = MagicMock()
        col = MagicMock()
        col.name = "idp_knowledge_base"
        mock_client.get_collections.return_value.collections = [col]
        mock_client.count.return_value.count = 0
        mock_client_fn.return_value = mock_client

        from app.services.rag import is_knowledge_base_populated
        assert is_knowledge_base_populated() is False

    @patch("app.services.rag._get_qdrant_client")
    def test_returns_true_when_collection_has_documents(self, mock_client_fn):
        mock_client = MagicMock()
        col = MagicMock()
        col.name = "idp_knowledge_base"
        mock_client.get_collections.return_value.collections = [col]
        mock_client.count.return_value.count = 42
        mock_client_fn.return_value = mock_client

        from app.services.rag import is_knowledge_base_populated
        assert is_knowledge_base_populated() is True

    @patch("app.services.rag._get_qdrant_client")
    def test_returns_false_on_exception(self, mock_client_fn):
        mock_client_fn.side_effect = Exception("Qdrant connection failed")

        from app.services.rag import is_knowledge_base_populated
        assert is_knowledge_base_populated() is False


# ── query_knowledge_base ──────────────────────────────────────────

class TestQueryKnowledgeBase:

    @patch("app.services.rag._get_vector_store")
    def test_returns_list_of_documents(self, mock_vs):
        doc1 = _make_langchain_doc("B.Tech requires 45% in PCM.", "eligibility_rules.txt")
        doc2 = _make_langchain_doc("CBSE roll number is 8-digit.", "board_formats.txt")

        mock_store = MagicMock()
        mock_store.similarity_search.return_value = [doc1, doc2]
        mock_vs.return_value = mock_store

        from app.services.rag import query_knowledge_base
        results = query_knowledge_base("minimum percentage for B.Tech")

        assert len(results) == 2
        assert results[0].page_content == "B.Tech requires 45% in PCM."

    @patch("app.services.rag._get_vector_store")
    def test_uses_top_k_4(self, mock_vs):
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []
        mock_vs.return_value = mock_store

        from app.services.rag import query_knowledge_base, TOP_K
        query_knowledge_base("test query")

        mock_store.similarity_search.assert_called_once_with("test query", k=TOP_K)
        assert TOP_K == 4

    @patch("app.services.rag._get_vector_store")
    def test_returns_empty_list_when_no_results(self, mock_vs):
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []
        mock_vs.return_value = mock_store

        from app.services.rag import query_knowledge_base
        results = query_knowledge_base("some query with no matching docs")

        assert results == []


# ── check_eligibility ─────────────────────────────────────────────

class TestCheckEligibility:

    def _mock_rag_response(self, eligible: bool, reason: str, confidence: float = 0.9):
        """Build the JSON string that GPT-4o returns."""
        return json.dumps({
            "eligible": eligible,
            "reason": reason,
            "confidence": confidence,
            "applicable_rule": "Minimum 45% in 12th PCM for B.Tech",
        })

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_eligible_student_returns_true(self, mock_oai, mock_rag):
        mock_rag.return_value = [_make_langchain_doc("B.Tech requires 45% PCM.")]

        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(
            eligible=True,
            reason="Student has 82% in PCM, meeting the 45% minimum.",
        )
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        result = check_eligibility(
            course="B.Tech",
            pct_10th=78.0,
            pct_12th=82.0,
            stream="Science",
            result_12th="PASS",
        )

        assert result["eligible"] is True
        assert "82%" in result["reason"] or "45%" in result["reason"]
        assert result["confidence"] == 0.9

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_ineligible_student_returns_false(self, mock_oai, mock_rag):
        mock_rag.return_value = [_make_langchain_doc("B.Tech requires 45% PCM.")]

        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(
            eligible=False,
            reason="Student has only 38% in 12th, below the 45% minimum for B.Tech.",
            confidence=0.95,
        )
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        result = check_eligibility(
            course="B.Tech",
            pct_10th=55.0,
            pct_12th=38.0,
            stream="Science",
            result_12th="PASS",
        )

        assert result["eligible"] is False
        assert result["confidence"] == 0.95

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_result_includes_context_used(self, mock_oai, mock_rag):
        mock_rag.return_value = [
            _make_langchain_doc("Rule 1", "eligibility_rules.txt"),
            _make_langchain_doc("Rule 2", "faq.txt"),
        ]
        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(True, "Eligible.")
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        result = check_eligibility("BBA", 65.0, 70.0, "Commerce", "PASS")

        assert "context_used" in result
        assert "eligibility_rules.txt" in result["context_used"]
        assert "faq.txt" in result["context_used"]

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_handles_none_percentage_values(self, mock_oai, mock_rag):
        mock_rag.return_value = []
        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(
            eligible=None,
            reason="Insufficient data to determine eligibility.",
            confidence=0.3,
        )
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        # Should not raise even with None values
        result = check_eligibility("B.Tech", None, None, None, None)
        assert "eligible" in result

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_openai_failure_returns_safe_fallback(self, mock_oai, mock_rag):
        mock_rag.return_value = []
        mock_oai.chat.completions.create.side_effect = Exception("OpenAI API error")

        from app.services.rag import check_eligibility
        result = check_eligibility("B.Tech", 75.0, 80.0, "Science", "PASS")

        assert result["eligible"] is None
        assert result["confidence"] == 0.0
        assert "could not be completed" in result["reason"]

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_uses_gpt4o_temperature_zero(self, mock_oai, mock_rag):
        """Eligibility decisions must use temperature=0 for determinism."""
        mock_rag.return_value = []
        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(True, "Eligible.")
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        check_eligibility("BBA", 60.0, 65.0, "Arts", "PASS")

        call_kwargs = mock_oai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0

    @patch("app.services.rag.query_knowledge_base")
    @patch("app.services.rag.openai_client")
    def test_prompt_includes_student_profile(self, mock_oai, mock_rag):
        """Verify the prompt sent to GPT-4o contains the student's actual data."""
        mock_rag.return_value = [_make_langchain_doc("Some rule.")]
        mock_choice = MagicMock()
        mock_choice.message.content = self._mock_rag_response(True, "Eligible.")
        mock_oai.chat.completions.create.return_value.choices = [mock_choice]

        from app.services.rag import check_eligibility
        check_eligibility(
            course="B.Sc",
            pct_10th=60.0,
            pct_12th=72.5,
            stream="Science",
            result_12th="PASS",
        )

        call_args = mock_oai.chat.completions.create.call_args[1]
        user_content = call_args["messages"][1]["content"]
        assert "72.5" in user_content
        assert "60.0" in user_content
        assert "Science" in user_content
        assert "B.Sc" in user_content


# ── Integration: verify.py RAG hook ──────────────────────────────

def _make_async_db(extraction_rows, doc_rows, existing_val=None):
    """Build an async-compatible DB session mock."""
    from app.models.document import DocumentStatus

    def make_result(items, scalar_val=None):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items
        r.scalar_one_or_none.return_value = scalar_val
        return r

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=[
        make_result(extraction_rows),           # ExtractionResult query
        make_result(doc_rows),                  # Document status query
        make_result([], scalar_val=existing_val),  # ValidationResult query
    ])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    return mock_db


class TestVerifyRouterRagIntegration:
    """Verify that _run_validation_task correctly wires the RAG result into checks."""

    @pytest.mark.asyncio
    @patch("app.routers.verify.is_knowledge_base_populated", return_value=True)
    @patch("app.routers.verify.check_eligibility")
    @patch("app.routers.verify.run_validation")
    @patch("app.routers.verify.AsyncSessionLocal")
    async def test_rag_check_appended_to_validation_checks(
        self, mock_session_cls, mock_run_val, mock_check_elig, mock_kb_populated
    ):
        from app.models.document import DocumentStatus, DocumentType

        mock_ext_row = MagicMock()
        mock_ext_row.application_id = "app-001"
        mock_ext_row.doc_type = DocumentType.MARKSHEET_12TH
        mock_ext_row.extracted_data = json.dumps({
            "percentage": {"value": "82.0", "confidence": 0.9},
            "stream":     {"value": "Science", "confidence": 0.9},
            "result":     {"value": "PASS",    "confidence": 0.99},
        })
        mock_ext_row.confidence_score = 0.9

        mock_10th_row = MagicMock()
        mock_10th_row.application_id = "app-001"
        mock_10th_row.doc_type = DocumentType.MARKSHEET_10TH
        mock_10th_row.extracted_data = json.dumps({
            "percentage": {"value": "75.0", "confidence": 0.9},
        })
        mock_10th_row.confidence_score = 0.9

        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.EXTRACTED

        mock_db = _make_async_db([mock_ext_row, mock_10th_row], [mock_doc])
        mock_session_cls.return_value = mock_db

        mock_run_val.return_value = {
            "checks": [{"check_name": "marks_check", "status": "PASS", "detail": "OK"}],
            "overall_score": 0.9,
            "decision": "APPROVED",
            "decision_reason": "All checks passed",
        }
        mock_check_elig.return_value = {
            "eligible": True,
            "reason": "Student meets 45% PCM requirement.",
            "confidence": 0.95,
            "applicable_rule": "B.Tech min 45% PCM",
        }

        from app.routers.verify import _run_validation_task
        await _run_validation_task("app-001")

        mock_check_elig.assert_called_once()
        mock_db.add.assert_called_once()
        saved_val = mock_db.add.call_args[0][0]
        saved_checks = json.loads(saved_val.checks)

        rag_check = next(
            (c for c in saved_checks if c["check_name"] == "rag_eligibility_check"), None
        )
        assert rag_check is not None
        assert rag_check["status"] == "PASS"

    @pytest.mark.asyncio
    @patch("app.routers.verify.is_knowledge_base_populated", return_value=False)
    @patch("app.routers.verify.check_eligibility")
    @patch("app.routers.verify.run_validation")
    @patch("app.routers.verify.AsyncSessionLocal")
    async def test_rag_skipped_when_kb_not_populated(
        self, mock_session_cls, mock_run_val, mock_check_elig, mock_kb_populated
    ):
        from app.models.document import DocumentStatus, DocumentType

        mock_ext_row = MagicMock()
        mock_ext_row.doc_type = DocumentType.MARKSHEET_12TH
        mock_ext_row.extracted_data = json.dumps({"percentage": {"value": "80", "confidence": 0.9}})
        mock_ext_row.confidence_score = 0.9

        mock_doc = MagicMock()
        mock_doc.status = DocumentStatus.EXTRACTED

        mock_db = _make_async_db([mock_ext_row], [mock_doc])
        mock_session_cls.return_value = mock_db

        mock_run_val.return_value = {
            "checks": [],
            "overall_score": 0.8,
            "decision": "APPROVED",
            "decision_reason": "OK",
        }

        from app.routers.verify import _run_validation_task
        await _run_validation_task("app-002")

        mock_check_elig.assert_not_called()
