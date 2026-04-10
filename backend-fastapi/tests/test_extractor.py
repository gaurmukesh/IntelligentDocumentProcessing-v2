"""
Unit tests for Phase 3 — Document Extraction Service

OpenAI API calls are mocked — no real API key needed.

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_extractor.py -v
"""

import io
import json
import base64
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.document import DocumentType
from app.services.extractor import (
    file_to_base64,
    _calculate_overall_confidence,
    extract_document,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_image_file(tmp_path):
    """Create a small valid PNG file."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    path = tmp_path / "test_image.png"
    img.save(str(path))
    return str(path)

@pytest.fixture
def sample_jpg_file(tmp_path):
    """Create a small valid JPG file."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    path = tmp_path / "test_image.jpg"
    img.save(str(path), format="JPEG")
    return str(path)

@pytest.fixture
def sample_pdf_file(tmp_path):
    """Create a minimal valid PDF file."""
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    path = tmp_path / "test.pdf"
    with open(path, "wb") as f:
        writer.write(f)
    return str(path)

@pytest.fixture
def mock_10th_response():
    return {
        "student_name":         {"value": "Rahul Sharma",  "confidence": 0.95},
        "date_of_birth":        {"value": "15/08/2003",    "confidence": 0.92},
        "board":                {"value": "CBSE",           "confidence": 0.98},
        "exam_year":            {"value": "2019",           "confidence": 0.97},
        "subjects": [
            {"name": "Mathematics", "marks_obtained": "92", "max_marks": "100", "confidence": 0.96},
            {"name": "Science",     "marks_obtained": "88", "max_marks": "100", "confidence": 0.95},
        ],
        "total_marks_obtained": {"value": "392",  "confidence": 0.94},
        "total_max_marks":      {"value": "500",  "confidence": 0.94},
        "percentage":           {"value": "78.4", "confidence": 0.94},
        "result":               {"value": "PASS", "confidence": 0.99},
        "grade":                {"value": "A",    "confidence": 0.90},
    }

@pytest.fixture
def mock_12th_response():
    return {
        "student_name":         {"value": "Rahul Sharma",  "confidence": 0.93},
        "date_of_birth":        {"value": "15/08/2003",    "confidence": 0.90},
        "board":                {"value": "CBSE",           "confidence": 0.97},
        "stream":               {"value": "Science",        "confidence": 0.96},
        "exam_year":            {"value": "2021",           "confidence": 0.98},
        "subjects": [
            {"name": "Physics",  "marks_obtained": "85", "max_marks": "100", "confidence": 0.94},
            {"name": "Chemistry","marks_obtained": "80", "max_marks": "100", "confidence": 0.93},
        ],
        "total_marks_obtained": {"value": "413",  "confidence": 0.91},
        "total_max_marks":      {"value": "500",  "confidence": 0.91},
        "percentage":           {"value": "82.6", "confidence": 0.91},
        "result":               {"value": "PASS", "confidence": 0.99},
        "grade":                {"value": "A",    "confidence": 0.89},
    }

@pytest.fixture
def mock_aadhar_response():
    return {
        "full_name":     {"value": "Rahul Sharma", "confidence": 0.96},
        "date_of_birth": {"value": "15/08/2003",   "confidence": 0.94},
        "gender":        {"value": "Male",          "confidence": 0.99},
        "aadhar_last4":  {"value": "4521",          "confidence": 0.98},
        "address":       {"value": "123, MG Road, Indore, MP - 452001", "confidence": 0.85},
        "is_front_side": {"value": "true",          "confidence": 0.97},
    }


# ── file_to_base64 tests ──────────────────────────────────────────

class TestFileToBase64:

    def test_png_returns_image_png_media_type(self, sample_image_file):
        b64, media_type = file_to_base64(sample_image_file)
        assert media_type == "image/png"
        assert len(b64) > 0

    def test_jpg_returns_image_jpeg_media_type(self, sample_jpg_file):
        b64, media_type = file_to_base64(sample_jpg_file)
        assert media_type == "image/jpeg"
        assert len(b64) > 0

    def test_base64_is_valid_encoding(self, sample_image_file):
        b64, _ = file_to_base64(sample_image_file)
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_pdf_returns_base64(self, sample_pdf_file):
        b64, media_type = file_to_base64(sample_pdf_file)
        assert len(b64) > 0
        # media_type is either application/pdf or image/png depending on pdf2image availability
        assert media_type in ("application/pdf", "image/png")

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            file_to_base64("/nonexistent/path/file.pdf")


# ── _calculate_overall_confidence tests ──────────────────────────

class TestCalculateOverallConfidence:

    def test_all_high_confidence(self):
        data = {
            "student_name": {"value": "John", "confidence": 0.95},
            "date_of_birth": {"value": "01/01/2000", "confidence": 0.90},
            "percentage": {"value": "85", "confidence": 0.88},
        }
        score = _calculate_overall_confidence(data)
        assert 0.87 <= score <= 0.92

    def test_all_zero_confidence(self):
        data = {
            "student_name": {"value": None, "confidence": 0.0},
            "date_of_birth": {"value": None, "confidence": 0.0},
        }
        assert _calculate_overall_confidence(data) == 0.0

    def test_empty_data_returns_zero(self):
        assert _calculate_overall_confidence({}) == 0.0

    def test_includes_list_field_confidences(self):
        data = {
            "student_name": {"value": "John", "confidence": 1.0},
            "subjects": [
                {"name": "Math", "marks_obtained": "90", "max_marks": "100", "confidence": 0.9},
                {"name": "Science", "marks_obtained": "85", "max_marks": "100", "confidence": 0.8},
            ],
        }
        score = _calculate_overall_confidence(data)
        # Average of 1.0, 0.9, 0.8 = 0.9
        assert abs(score - 0.9) < 0.01

    def test_confidence_is_rounded_to_3_decimal_places(self):
        data = {"field": {"value": "x", "confidence": 0.9876543}}
        score = _calculate_overall_confidence(data)
        assert len(str(score).split(".")[-1]) <= 3


# ── extract_document tests (mocked OpenAI) ────────────────────────

class TestExtractDocument:

    def _mock_openai_response(self, response_dict: dict):
        """Create a mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(response_dict)
        return mock_response

    def test_extract_10th_marksheet(self, sample_image_file, mock_10th_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_10th_response)
            data, confidence = extract_document(sample_image_file, DocumentType.MARKSHEET_10TH)

        assert data["student_name"]["value"] == "Rahul Sharma"
        assert data["percentage"]["value"] == "78.4"
        assert data["result"]["value"] == "PASS"
        assert 0.0 < confidence <= 1.0

    def test_extract_12th_marksheet(self, sample_image_file, mock_12th_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_12th_response)
            data, confidence = extract_document(sample_image_file, DocumentType.MARKSHEET_12TH)

        assert data["student_name"]["value"] == "Rahul Sharma"
        assert data["stream"]["value"] == "Science"
        assert data["percentage"]["value"] == "82.6"

    def test_extract_aadhar(self, sample_image_file, mock_aadhar_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_aadhar_response)
            data, confidence = extract_document(sample_image_file, DocumentType.AADHAR)

        assert data["full_name"]["value"] == "Rahul Sharma"
        assert data["aadhar_last4"]["value"] == "4521"
        assert data["gender"]["value"] == "Male"

    def test_returns_confidence_score(self, sample_image_file, mock_10th_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_10th_response)
            _, confidence = extract_document(sample_image_file, DocumentType.MARKSHEET_10TH)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_unsupported_doc_type_raises(self, sample_image_file):
        with pytest.raises(ValueError, match="Unsupported document type"):
            extract_document(sample_image_file, "UNKNOWN_TYPE")

    def test_openai_api_error_propagates(self, sample_image_file):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API timeout")
            with pytest.raises(Exception, match="API timeout"):
                extract_document(sample_image_file, DocumentType.MARKSHEET_10TH)

    def test_extract_calls_openai_once_per_document(self, sample_image_file, mock_10th_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_10th_response)
            extract_document(sample_image_file, DocumentType.MARKSHEET_10TH)
            assert mock_client.chat.completions.create.call_count == 1

    def test_pdf_extraction_triggers_pdf_handler(self, sample_pdf_file, mock_10th_response):
        with patch("app.services.extractor.client") as mock_client:
            mock_client.chat.completions.create.return_value = \
                self._mock_openai_response(mock_10th_response)
            data, confidence = extract_document(sample_pdf_file, DocumentType.MARKSHEET_10TH)
        assert data is not None
        assert confidence >= 0.0
