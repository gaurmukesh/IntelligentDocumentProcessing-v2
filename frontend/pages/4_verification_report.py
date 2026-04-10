"""
Page 4 — Verification Report

Fetches the full report from FastAPI /verify/{id}/report and displays:
  - Overall decision + score
  - Validation checks (PASS / FAIL / WARNING)
  - Per-document extracted fields with confidence
  - RAG eligibility check result
"""

import streamlit as st
from utils.api import get_verification_report

st.set_page_config(page_title="Verification Report", page_icon="📊", layout="wide")
st.title("Verification Report")

# ── Application ID input ──────────────────────────────────────────

default_id = st.session_state.get("selected_app_id", "")
app_id = st.text_input("Application ID", value=default_id, placeholder="Paste application ID here")

if not app_id:
    st.info("Enter an Application ID to view its verification report.")
    st.stop()

if st.button("Load Report", type="primary"):
    st.session_state["selected_app_id"] = app_id
    st.session_state["report_data"] = None

# ── Fetch report ──────────────────────────────────────────────────

try:
    report = get_verification_report(app_id)
    st.session_state["report_data"] = report
except Exception as e:
    if "404" in str(e):
        st.warning("Report not available yet. The verification pipeline may still be running.")
        st.info("Go to **Pipeline Status** to track progress.")
    else:
        st.error(f"Could not fetch report: {e}")
    st.stop()

# ── Overall decision ──────────────────────────────────────────────

st.divider()

decision = report.get("status", "")
score = report.get("overall_score")
reason = report.get("decision_reason", "")

DECISION_STYLE = {
    "APPROVED":      ("success", "✅ APPROVED"),
    "REJECTED":      ("error",   "❌ REJECTED"),
    "MANUAL_REVIEW": ("warning", "🔍 MANUAL REVIEW REQUIRED"),
}
style, text = DECISION_STYLE.get(decision, ("info", decision or "Pending"))

getattr(st, style)(f"## {text}")

col1, col2 = st.columns(2)
with col1:
    if score is not None:
        st.metric("Overall Score", f"{score:.0%}")
with col2:
    if reason:
        st.markdown(f"**Decision Reason**\n\n{reason}")

# ── Validation checks ─────────────────────────────────────────────

st.divider()
st.subheader("Validation Checks")

validation = report.get("validation", {})
checks = validation.get("checks", []) if validation else []

if not checks:
    st.info("No validation checks available.")
else:
    CHECK_ICONS = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️"}

    for check in checks:
        name = check.get("check_name", "").replace("_", " ").title()
        status = check.get("status", "")
        detail = check.get("detail", "")
        confidence = check.get("confidence")
        icon = CHECK_ICONS.get(status, "⬜")

        with st.expander(f"{icon} {name} — **{status}**", expanded=(status == "FAIL")):
            st.markdown(detail)
            if confidence is not None:
                st.progress(confidence, text=f"Confidence: {confidence:.0%}")

# ── Extracted document data ───────────────────────────────────────

st.divider()
st.subheader("Extracted Document Data")

documents = report.get("documents", [])

DOC_LABELS = {
    "MARKSHEET_10TH": "10th Marksheet",
    "MARKSHEET_12TH": "12th Marksheet",
    "AADHAR":         "Aadhar Card",
}

FIELD_LABELS = {
    "student_name":      "Student Name",
    "date_of_birth":     "Date of Birth",
    "board":             "Board",
    "stream":            "Stream",
    "exam_year":         "Exam Year",
    "percentage":        "Percentage",
    "result":            "Result",
    "aadhar_number":     "Aadhar Number",
    "gender":            "Gender",
    "father_name":       "Father's Name",
    "address":           "Address",
}

if not documents:
    st.info("No extraction data available.")
else:
    tabs = st.tabs([DOC_LABELS.get(d.get("doc_type", ""), d.get("doc_type", "")) for d in documents])

    for tab, doc in zip(tabs, documents):
        with tab:
            doc_type = doc.get("doc_type", "")
            confidence = doc.get("confidence_score")
            error = doc.get("error_message")

            if error:
                st.error(f"Extraction failed: {error}")
                continue

            if confidence is not None:
                colour = "green" if confidence >= 0.80 else ("orange" if confidence >= 0.60 else "red")
                st.markdown(f"**Overall confidence:** :{colour}[{confidence:.0%}]")
                st.progress(confidence)

            extracted = doc.get("extracted_data") or {}
            if not extracted:
                st.info("No data extracted.")
                continue

            st.divider()

            # Display each field
            for field_key, field_data in extracted.items():
                label = FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())

                if isinstance(field_data, dict):
                    value = field_data.get("value", "—")
                    field_conf = field_data.get("confidence")
                else:
                    value = field_data
                    field_conf = None

                col1, col2, col3 = st.columns([3, 4, 2])
                with col1:
                    st.markdown(f"**{label}**")
                with col2:
                    st.markdown(str(value) if value is not None else "—")
                with col3:
                    if field_conf is not None:
                        badge_colour = "green" if field_conf >= 0.8 else ("orange" if field_conf >= 0.6 else "red")
                        st.markdown(f":{badge_colour}[{field_conf:.0%}]")

# ── RAG eligibility check highlight ──────────────────────────────

rag_check = next(
    (c for c in checks if c.get("check_name") == "rag_eligibility_check"),
    None
) if checks else None

if rag_check:
    st.divider()
    st.subheader("RAG Eligibility Check")

    rag_status = rag_check.get("status", "")
    rag_detail = rag_check.get("detail", "")
    rag_conf = rag_check.get("confidence")

    if rag_status == "PASS":
        st.success(f"**Eligible** — {rag_detail}")
    elif rag_status == "FAIL":
        st.error(f"**Not Eligible** — {rag_detail}")
    else:
        st.warning(f"**Uncertain** — {rag_detail}")

    if rag_conf is not None:
        st.metric("RAG Confidence", f"{rag_conf:.0%}")
