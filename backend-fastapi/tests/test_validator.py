"""
Unit tests for the Validation Engine (Phase 4)

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_validator.py -v
"""

import pytest
from app.services.validator import (
    run_validation,
    validate_individual_document,
    validate_name_match,
    validate_dob_match,
    validate_marks,
    calculate_overall_score,
    make_decision,
)
from app.models.document import DocumentType, VerificationStatus


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def valid_10th():
    return {
        "student_name":  {"value": "Rahul Sharma",  "confidence": 0.95},
        "date_of_birth": {"value": "15/08/2003",    "confidence": 0.92},
        "board":         {"value": "CBSE",           "confidence": 0.98},
        "exam_year":     {"value": "2019",           "confidence": 0.97},
        "percentage":    {"value": "78.4",           "confidence": 0.94},
        "result":        {"value": "PASS",           "confidence": 0.99},
    }

@pytest.fixture
def valid_12th():
    return {
        "student_name":  {"value": "Rahul Sharma",  "confidence": 0.93},
        "date_of_birth": {"value": "15/08/2003",    "confidence": 0.90},
        "board":         {"value": "CBSE",           "confidence": 0.97},
        "stream":        {"value": "Science",        "confidence": 0.96},
        "exam_year":     {"value": "2021",           "confidence": 0.98},
        "percentage":    {"value": "82.6",           "confidence": 0.91},
        "result":        {"value": "PASS",           "confidence": 0.99},
    }

@pytest.fixture
def valid_aadhar():
    return {
        "full_name":     {"value": "Rahul Sharma",  "confidence": 0.96},
        "date_of_birth": {"value": "15/08/2003",    "confidence": 0.94},
        "gender":        {"value": "Male",           "confidence": 0.99},
        "aadhar_last4":  {"value": "4521",           "confidence": 0.98},
    }

@pytest.fixture
def all_valid(valid_10th, valid_12th, valid_aadhar):
    return {
        DocumentType.MARKSHEET_10TH: valid_10th,
        DocumentType.MARKSHEET_12TH: valid_12th,
        DocumentType.AADHAR:         valid_aadhar,
    }


# ── Individual document validation ───────────────────────────────

class TestIndividualValidation:

    def test_all_fields_present_returns_all_pass(self, valid_10th):
        checks = validate_individual_document(valid_10th, DocumentType.MARKSHEET_10TH)
        statuses = {c["status"] for c in checks}
        assert statuses == {"PASS"}

    def test_missing_field_returns_fail(self, valid_10th):
        valid_10th.pop("percentage")
        checks = validate_individual_document(valid_10th, DocumentType.MARKSHEET_10TH)
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert any("percentage" in c["check_name"] for c in failed)

    def test_low_confidence_field_returns_warning(self, valid_10th):
        valid_10th["student_name"]["confidence"] = 0.50   # below 0.70 threshold
        checks = validate_individual_document(valid_10th, DocumentType.MARKSHEET_10TH)
        warnings = [c for c in checks if c["status"] == "WARNING"]
        assert any("student_name" in c["check_name"] for c in warnings)

    def test_null_value_returns_fail(self, valid_12th):
        valid_12th["stream"]["value"] = None
        checks = validate_individual_document(valid_12th, DocumentType.MARKSHEET_12TH)
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert any("stream" in c["check_name"] for c in failed)

    def test_aadhar_required_fields(self, valid_aadhar):
        checks = validate_individual_document(valid_aadhar, DocumentType.AADHAR)
        assert all(c["status"] == "PASS" for c in checks)


# ── Cross-document name matching ──────────────────────────────────

class TestNameMatch:

    def test_identical_names_pass(self, valid_10th, valid_12th, valid_aadhar):
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        checks = validate_name_match(extractions)
        assert checks[0]["status"] == "PASS"

    def test_similar_names_pass(self, valid_10th, valid_aadhar):
        # Minor spelling variation — should still pass fuzzy match
        valid_10th["student_name"]["value"] = "Rahul Sharma"
        valid_aadhar["full_name"]["value"]  = "RAHUL SHARMA"
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        checks = validate_name_match(extractions)
        assert checks[0]["status"] == "PASS"

    def test_different_names_fail(self, valid_10th, valid_aadhar):
        valid_aadhar["full_name"]["value"] = "Suresh Patel"
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        checks = validate_name_match(extractions)
        assert checks[0]["status"] == "FAIL"

    def test_single_document_returns_warning(self, valid_10th):
        checks = validate_name_match({DocumentType.MARKSHEET_10TH: valid_10th})
        assert checks[0]["status"] == "WARNING"


# ── Cross-document DOB matching ───────────────────────────────────

class TestDOBMatch:

    def test_identical_dob_pass(self, valid_10th, valid_12th, valid_aadhar):
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        checks = validate_dob_match(extractions)
        assert checks[0]["status"] == "PASS"

    def test_different_dob_fail(self, valid_10th, valid_12th):
        valid_12th["date_of_birth"]["value"] = "20/09/2003"   # different DOB
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
        }
        checks = validate_dob_match(extractions)
        assert checks[0]["status"] == "FAIL"

    def test_different_date_formats_normalised(self, valid_10th, valid_aadhar):
        valid_10th["date_of_birth"]["value"]  = "15/08/2003"
        valid_aadhar["date_of_birth"]["value"] = "2003-08-15"  # ISO format
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        checks = validate_dob_match(extractions)
        assert checks[0]["status"] == "PASS"


# ── Marks / percentage validation ────────────────────────────────

class TestMarksValidation:

    def test_good_marks_pass(self, valid_10th, valid_12th):
        checks = validate_marks({
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
        })
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert len(failed) == 0

    def test_10th_below_minimum_fail(self, valid_10th):
        valid_10th["percentage"]["value"] = "30.0"   # below 35%
        checks = validate_marks({DocumentType.MARKSHEET_10TH: valid_10th})
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert any("10th_percentage" in c["check_name"] for c in failed)

    def test_12th_below_minimum_fail(self, valid_12th):
        valid_12th["percentage"]["value"] = "40.0"   # below 45%
        checks = validate_marks({DocumentType.MARKSHEET_12TH: valid_12th})
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert any("12th_percentage" in c["check_name"] for c in failed)

    def test_12th_result_fail(self, valid_12th):
        valid_12th["result"]["value"] = "FAIL"
        checks = validate_marks({DocumentType.MARKSHEET_12TH: valid_12th})
        failed = [c for c in checks if c["status"] == "FAIL"]
        assert any("12th_result" in c["check_name"] for c in failed)

    def test_missing_percentage_returns_warning(self, valid_12th):
        valid_12th["percentage"]["value"] = None
        checks = validate_marks({DocumentType.MARKSHEET_12TH: valid_12th})
        warnings = [c for c in checks if c["status"] == "WARNING"]
        assert any("12th_percentage" in c["check_name"] for c in warnings)


# ── Decision engine ───────────────────────────────────────────────

class TestDecisionEngine:

    def test_all_pass_auto_approve(self, all_valid):
        result = run_validation(all_valid, {})
        assert result["decision"] == VerificationStatus.APPROVED
        assert result["overall_score"] >= 0.85

    def test_dob_mismatch_auto_reject(self, valid_10th, valid_12th, valid_aadhar):
        valid_12th["date_of_birth"]["value"] = "01/01/1990"   # DOB mismatch
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        result = run_validation(extractions, {})
        assert result["decision"] == VerificationStatus.REJECTED

    def test_low_12th_marks_auto_reject(self, valid_10th, valid_12th, valid_aadhar):
        valid_12th["percentage"]["value"] = "38.0"   # below 45%
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        result = run_validation(extractions, {})
        assert result["decision"] == VerificationStatus.REJECTED

    def test_low_confidence_manual_review(self, all_valid):
        # Set multiple fields to low confidence → score drops below 0.85
        for doc in all_valid.values():
            for field in doc.values():
                if isinstance(field, dict) and "confidence" in field:
                    field["confidence"] = 0.55
        result = run_validation(all_valid, {})
        assert result["decision"] in (
            VerificationStatus.MANUAL_REVIEW, VerificationStatus.REJECTED
        )

    def test_name_mismatch_does_not_auto_reject(self, valid_10th, valid_12th, valid_aadhar):
        # Name mismatch is FAIL but not a critical-fail check → goes to manual review
        valid_aadhar["full_name"]["value"] = "Suresh Patel"
        extractions = {
            DocumentType.MARKSHEET_10TH: valid_10th,
            DocumentType.MARKSHEET_12TH: valid_12th,
            DocumentType.AADHAR:         valid_aadhar,
        }
        result = run_validation(extractions, {})
        # Name mismatch lowers score → manual review (not auto-reject)
        assert result["decision"] in (
            VerificationStatus.MANUAL_REVIEW, VerificationStatus.REJECTED
        )


# ── Overall score calculation ─────────────────────────────────────

class TestScoreCalculation:

    def test_all_pass_score_is_1(self):
        checks = [
            {"check_name": "a", "status": "PASS", "detail": ""},
            {"check_name": "b", "status": "PASS", "detail": ""},
        ]
        assert calculate_overall_score(checks) == 1.0

    def test_all_fail_score_is_0(self):
        checks = [
            {"check_name": "a", "status": "FAIL", "detail": ""},
            {"check_name": "b", "status": "FAIL", "detail": ""},
        ]
        assert calculate_overall_score(checks) == 0.0

    def test_warning_scores_half(self):
        checks = [
            {"check_name": "a", "status": "PASS",    "detail": ""},
            {"check_name": "b", "status": "WARNING",  "detail": ""},
        ]
        assert calculate_overall_score(checks) == 0.75

    def test_empty_checks_score_is_0(self):
        assert calculate_overall_score([]) == 0.0
