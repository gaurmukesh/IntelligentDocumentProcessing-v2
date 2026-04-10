"""
Validation Engine — Phase 4

Runs three layers of validation:
1. Individual document checks  (completeness, confidence)
2. Cross-document checks       (name match, DOB match)
3. Eligibility checks          (marks/percentage thresholds)

Returns a ValidationResult with all checks, overall score, and final decision.
"""

import json
import re
from datetime import datetime
from typing import Optional
from thefuzz import fuzz

from app.models.document import DocumentType, VerificationStatus

# ── Thresholds (configurable) ─────────────────────────────────────
CONFIDENCE_LOW_THRESHOLD = 0.70       # fields below this are flagged
NAME_FUZZY_THRESHOLD = 80             # minimum fuzzy match score for names
MIN_10TH_PERCENTAGE = 35.0            # minimum % to pass 10th eligibility
MIN_12TH_PERCENTAGE = 45.0            # minimum % to pass 12th eligibility
AUTO_APPROVE_SCORE = 0.85             # overall score ≥ this → auto approve
MANUAL_REVIEW_SCORE = 0.60            # overall score between this and auto_approve → manual review
                                       # below manual_review_score → auto reject


# ── Check result builder ──────────────────────────────────────────

def _check(name: str, status: str, detail: str, confidence: Optional[float] = None) -> dict:
    return {
        "check_name": name,
        "status": status,       # PASS | FAIL | WARNING
        "detail": detail,
        "confidence": confidence,
    }


# ── Individual document validation ───────────────────────────────

REQUIRED_FIELDS = {
    DocumentType.MARKSHEET_10TH: [
        "student_name", "date_of_birth", "board", "exam_year",
        "percentage", "result"
    ],
    DocumentType.MARKSHEET_12TH: [
        "student_name", "date_of_birth", "board", "stream",
        "exam_year", "percentage", "result"
    ],
    DocumentType.AADHAR: [
        "full_name", "date_of_birth", "gender", "aadhar_last4"
    ],
}


def validate_individual_document(extracted_data: dict, doc_type: DocumentType) -> list[dict]:
    checks = []
    required = REQUIRED_FIELDS.get(doc_type, [])

    for field in required:
        field_data = extracted_data.get(field, {})
        value = field_data.get("value") if isinstance(field_data, dict) else field_data
        confidence = float(field_data.get("confidence", 0.0)) if isinstance(field_data, dict) else None

        # Check field presence
        if value is None or str(value).strip() == "" or str(value).lower() == "null":
            checks.append(_check(
                name=f"{doc_type.value}_field_{field}",
                status="FAIL",
                detail=f"Required field '{field}' is missing or empty in {doc_type.value}",
                confidence=0.0,
            ))
        elif confidence is not None and confidence < CONFIDENCE_LOW_THRESHOLD:
            checks.append(_check(
                name=f"{doc_type.value}_field_{field}",
                status="WARNING",
                detail=f"Field '{field}' extracted with low confidence ({confidence:.0%}) in {doc_type.value}",
                confidence=confidence,
            ))
        else:
            checks.append(_check(
                name=f"{doc_type.value}_field_{field}",
                status="PASS",
                detail=f"Field '{field}' extracted successfully",
                confidence=confidence,
            ))

    return checks


# ── Cross-document name matching ──────────────────────────────────

def _get_name(extracted: dict, doc_type: DocumentType) -> Optional[str]:
    if doc_type == DocumentType.AADHAR:
        field = extracted.get("full_name", {})
    else:
        field = extracted.get("student_name", {})
    if isinstance(field, dict):
        return field.get("value")
    return field


def validate_name_match(extractions: dict[DocumentType, dict]) -> list[dict]:
    """Compare names across all available documents using fuzzy matching."""
    checks = []
    names = {
        doc_type: _get_name(data, doc_type)
        for doc_type, data in extractions.items()
        if _get_name(data, doc_type)
    }

    if len(names) < 2:
        checks.append(_check(
            name="cross_doc_name_match",
            status="WARNING",
            detail="Not enough documents with names to perform cross-document name match",
        ))
        return checks

    doc_types = list(names.keys())
    all_match = True
    details = []

    for i in range(len(doc_types)):
        for j in range(i + 1, len(doc_types)):
            dt1, dt2 = doc_types[i], doc_types[j]
            name1, name2 = names[dt1], names[dt2]
            score = fuzz.token_sort_ratio(name1.upper(), name2.upper())
            match = score >= NAME_FUZZY_THRESHOLD
            if not match:
                all_match = False
            details.append(
                f"{dt1.value}: '{name1}' vs {dt2.value}: '{name2}' → {score}% match"
            )

    checks.append(_check(
        name="cross_doc_name_match",
        status="PASS" if all_match else "FAIL",
        detail=" | ".join(details),
        confidence=None,
    ))
    return checks


# ── Cross-document DOB matching ───────────────────────────────────

def _normalise_dob(dob_str: Optional[str]) -> Optional[str]:
    """Normalise DOB to DD/MM/YYYY for comparison."""
    if not dob_str:
        return None
    dob_str = dob_str.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(dob_str, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return dob_str   # return as-is if format unrecognised


def _get_dob(extracted: dict, doc_type: DocumentType) -> Optional[str]:
    field = extracted.get("date_of_birth", {})
    raw = field.get("value") if isinstance(field, dict) else field
    return _normalise_dob(raw)


def validate_dob_match(extractions: dict[DocumentType, dict]) -> list[dict]:
    """
    Compare DOB across all available documents.

    Aadhar is treated as the authoritative DOB source (government-issued biometric ID).
    - If all DOBs match               → PASS
    - If only marksheets disagree
      but Aadhar is present           → WARNING  (OCR misread likely; flag for manual review)
    - If Aadhar itself is missing
      and marksheets disagree         → FAIL
    """
    checks = []
    dobs = {
        doc_type: _get_dob(data, doc_type)
        for doc_type, data in extractions.items()
        if _get_dob(data, doc_type)
    }

    if len(dobs) < 2:
        checks.append(_check(
            name="cross_doc_dob_match",
            status="WARNING",
            detail="Not enough documents with DOB to perform cross-document DOB match",
        ))
        return checks

    unique_dobs = set(dobs.values())
    all_match = len(unique_dobs) == 1
    detail = " | ".join([f"{dt.value}: {dob}" for dt, dob in dobs.items()])

    if all_match:
        status = "PASS"
    elif DocumentType.AADHAR in dobs:
        # Aadhar is authoritative — mismatch is likely an OCR error on the marksheet
        aadhar_dob = dobs[DocumentType.AADHAR]
        detail = (
            f"{detail} — Aadhar ({aadhar_dob}) is authoritative; "
            "marksheet DOB may be an OCR misread. Manual verification recommended."
        )
        status = "WARNING"
    else:
        status = "FAIL"

    checks.append(_check(
        name="cross_doc_dob_match",
        status=status,
        detail=detail,
    ))
    return checks


# ── Marks / percentage validation ────────────────────────────────

def _get_percentage(extracted: dict) -> Optional[float]:
    field = extracted.get("percentage", {})
    raw = field.get("value") if isinstance(field, dict) else field
    if raw is None:
        return None
    try:
        return float(str(raw).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def validate_marks(extractions: dict[DocumentType, dict]) -> list[dict]:
    checks = []

    # 10th percentage
    if DocumentType.MARKSHEET_10TH in extractions:
        pct = _get_percentage(extractions[DocumentType.MARKSHEET_10TH])
        if pct is None:
            checks.append(_check(
                name="10th_percentage_eligibility",
                status="WARNING",
                detail="Could not extract 10th percentage for eligibility check",
            ))
        elif pct < MIN_10TH_PERCENTAGE:
            checks.append(_check(
                name="10th_percentage_eligibility",
                status="FAIL",
                detail=f"10th percentage {pct}% is below minimum required {MIN_10TH_PERCENTAGE}%",
            ))
        else:
            checks.append(_check(
                name="10th_percentage_eligibility",
                status="PASS",
                detail=f"10th percentage {pct}% meets minimum requirement of {MIN_10TH_PERCENTAGE}%",
            ))

    # 12th percentage
    if DocumentType.MARKSHEET_12TH in extractions:
        pct = _get_percentage(extractions[DocumentType.MARKSHEET_12TH])
        if pct is None:
            checks.append(_check(
                name="12th_percentage_eligibility",
                status="WARNING",
                detail="Could not extract 12th percentage for eligibility check",
            ))
        elif pct < MIN_12TH_PERCENTAGE:
            checks.append(_check(
                name="12th_percentage_eligibility",
                status="FAIL",
                detail=f"12th percentage {pct}% is below minimum required {MIN_12TH_PERCENTAGE}%",
            ))
        else:
            checks.append(_check(
                name="12th_percentage_eligibility",
                status="PASS",
                detail=f"12th percentage {pct}% meets minimum requirement of {MIN_12TH_PERCENTAGE}%",
            ))

    # 12th result (pass/fail)
    if DocumentType.MARKSHEET_12TH in extractions:
        result_field = extractions[DocumentType.MARKSHEET_12TH].get("result", {})
        result_val = result_field.get("value") if isinstance(result_field, dict) else result_field
        if result_val and str(result_val).upper() == "FAIL":
            checks.append(_check(
                name="12th_result_check",
                status="FAIL",
                detail="12th marksheet shows result as FAIL",
            ))
        elif result_val:
            checks.append(_check(
                name="12th_result_check",
                status="PASS",
                detail=f"12th result: {result_val}",
            ))

    return checks


# ── Confidence scoring ────────────────────────────────────────────

def calculate_overall_score(all_checks: list[dict]) -> float:
    """
    Score based on check outcomes:
    PASS    = 1.0
    WARNING = 0.5
    FAIL    = 0.0
    """
    if not all_checks:
        return 0.0
    scores = []
    for check in all_checks:
        if check["status"] == "PASS":
            scores.append(1.0)
        elif check["status"] == "WARNING":
            scores.append(0.5)
        else:
            scores.append(0.0)
    return round(sum(scores) / len(scores), 3)


# ── Decision engine ───────────────────────────────────────────────

def make_decision(all_checks: list[dict], overall_score: float) -> tuple[VerificationStatus, str]:
    """
    Returns (decision, reason).

    Auto-Reject triggers:
    - DOB mismatch (FAIL)
    - 12th result is FAIL
    - 12th or 10th percentage below minimum

    Manual Review triggers (regardless of score):
    - Name mismatch across documents

    Auto-Approve:
    - No critical failures, no manual review triggers, overall_score >= AUTO_APPROVE_SCORE

    Manual Review:
    - No critical failures but overall_score < AUTO_APPROVE_SCORE
    """
    critical_fail_checks = {
        "12th_result_check",
        "10th_percentage_eligibility",
        "12th_percentage_eligibility",
    }

    manual_review_trigger_checks = {
        "cross_doc_name_match",
        "cross_doc_dob_match",   # DOB mismatch → manual review (Aadhar is authoritative; may be OCR error)
    }

    failed_critical = [
        c for c in all_checks
        if c["status"] == "FAIL" and c["check_name"] in critical_fail_checks
    ]
    if failed_critical:
        reasons = "; ".join([c["detail"] for c in failed_critical])
        return VerificationStatus.REJECTED, f"Critical check(s) failed: {reasons}"

    failed_manual = [
        c for c in all_checks
        if c["status"] == "FAIL" and c["check_name"] in manual_review_trigger_checks
    ]
    if failed_manual:
        reasons = "; ".join([c["detail"] for c in failed_manual])
        return VerificationStatus.MANUAL_REVIEW, f"Requires manual review: {reasons}"

    if overall_score >= AUTO_APPROVE_SCORE:
        return VerificationStatus.APPROVED, f"All checks passed with score {overall_score:.0%}"

    if overall_score >= MANUAL_REVIEW_SCORE:
        low_confidence = [c for c in all_checks if c["status"] == "WARNING"]
        reasons = "; ".join([c["detail"] for c in low_confidence[:3]])
        return VerificationStatus.MANUAL_REVIEW, f"Score {overall_score:.0%} — requires manual review. {reasons}"

    return VerificationStatus.REJECTED, f"Overall score {overall_score:.0%} is too low for approval"


# ── Main validation entry point ───────────────────────────────────

def run_validation(
    extractions: dict[DocumentType, dict],
    doc_confidences: dict[DocumentType, float],
) -> dict:
    """
    Run all validation checks for an application.

    Args:
        extractions: {DocumentType: extracted_data_dict}
        doc_confidences: {DocumentType: overall_confidence_score}

    Returns:
        {
            "checks": [...],
            "overall_score": float,
            "decision": VerificationStatus,
            "decision_reason": str,
        }
    """
    all_checks = []

    # 1. Individual document validation
    for doc_type, data in extractions.items():
        all_checks.extend(validate_individual_document(data, doc_type))

    # 2. Cross-document name match
    all_checks.extend(validate_name_match(extractions))

    # 3. Cross-document DOB match
    all_checks.extend(validate_dob_match(extractions))

    # 4. Marks / percentage eligibility
    all_checks.extend(validate_marks(extractions))

    # 5. Overall score and decision
    overall_score = calculate_overall_score(all_checks)
    decision, reason = make_decision(all_checks, overall_score)

    return {
        "checks": all_checks,
        "overall_score": overall_score,
        "decision": decision,
        "decision_reason": reason,
    }
