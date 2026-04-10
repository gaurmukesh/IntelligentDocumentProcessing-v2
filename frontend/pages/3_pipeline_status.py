"""
Page 3 — Pipeline Status

Polls FastAPI /applications/{id}/pipeline-status every few seconds.
Shows pipeline stage, per-document status and confidence scores.
"""

import time
import streamlit as st
from utils.api import get_pipeline_status

st.set_page_config(page_title="Pipeline Status", page_icon="⚙️", layout="wide")
st.title("Pipeline Status")

# ── Application ID input ──────────────────────────────────────────

default_id = st.session_state.get("selected_app_id", "")
app_id = st.text_input("Application ID", value=default_id, placeholder="Paste application ID here")

if not app_id:
    st.info("Enter an Application ID to track its pipeline progress.")
    st.stop()

# ── Auto-refresh toggle ───────────────────────────────────────────

col1, col2 = st.columns([3, 1])
with col2:
    auto_refresh = st.toggle("Auto-refresh (5s)", value=False)

# ── Fetch status ──────────────────────────────────────────────────

try:
    data = get_pipeline_status(app_id)
except Exception as e:
    st.error(f"Could not fetch pipeline status: {e}")
    st.info("Make sure FastAPI is running on port 8000 and documents have been uploaded.")
    st.stop()

# ── Pipeline stage banner ─────────────────────────────────────────

STAGE_CONFIG = {
    "UPLOADING":   ("🔵", "Uploading",   "Documents are being uploaded."),
    "EXTRACTING":  ("🟡", "Extracting",  "AI is extracting data from documents…"),
    "VALIDATING":  ("🟡", "Validating",  "Running validation and RAG eligibility check…"),
    "COMPLETE":    ("🟢", "Complete",    "Verification pipeline finished."),
    "FAILED":      ("🔴", "Failed",      "One or more documents failed to process."),
}

stage = data.get("pipeline_stage", "UNKNOWN")
icon, label, detail = STAGE_CONFIG.get(stage, ("⬜", stage, ""))

if stage == "COMPLETE":
    st.success(f"{icon} **{label}** — {detail}")
elif stage == "FAILED":
    st.error(f"{icon} **{label}** — {detail}")
else:
    st.warning(f"{icon} **{label}** — {detail}")

# ── Stage progress bar ────────────────────────────────────────────

STAGE_ORDER = ["UPLOADING", "EXTRACTING", "VALIDATING", "COMPLETE"]
stage_progress = {s: i / (len(STAGE_ORDER) - 1) for i, s in enumerate(STAGE_ORDER)}
progress_val = stage_progress.get(stage, 0.0)
st.progress(progress_val)

st.divider()

# ── Per-document status ───────────────────────────────────────────

st.subheader("Documents")

DOC_LABELS = {
    "MARKSHEET_10TH": "10th Marksheet",
    "MARKSHEET_12TH": "12th Marksheet",
    "AADHAR":         "Aadhar Card",
}

STATUS_ICONS = {
    "PENDING":    "⏳",
    "EXTRACTING": "⚙️",
    "EXTRACTED":  "✅",
    "FAILED":     "❌",
}

docs = data.get("documents", [])
if not docs:
    st.info("No document records found yet.")
else:
    cols = st.columns(len(docs))
    for col, doc in zip(cols, docs):
        with col:
            doc_type = doc.get("doc_type", "")
            label = DOC_LABELS.get(doc_type, doc_type)
            upload_status = doc.get("upload_status", "PENDING")
            icon = STATUS_ICONS.get(upload_status, "⬜")
            confidence = doc.get("confidence_score")
            error = doc.get("extraction_error")

            st.markdown(f"### {icon} {label}")
            st.markdown(f"**Status:** {upload_status}")

            if confidence is not None:
                colour = "green" if confidence >= 0.80 else ("orange" if confidence >= 0.60 else "red")
                st.markdown(
                    f"**Confidence:** :{colour}[{confidence:.0%}]"
                )
                st.progress(confidence)

            if error:
                st.error(f"Error: {error}")

# ── Verification result (if complete) ────────────────────────────

verification = data.get("verification")
if verification:
    st.divider()
    st.subheader("Verification Result")

    decision = verification.get("decision", "")
    score = verification.get("overall_score")
    reason = verification.get("decision_reason", "")

    DECISION_STYLE = {
        "APPROVED":      ("success", "✅ APPROVED"),
        "REJECTED":      ("error",   "❌ REJECTED"),
        "MANUAL_REVIEW": ("warning", "🔍 MANUAL REVIEW"),
    }

    style, text = DECISION_STYLE.get(decision, ("info", decision))
    getattr(st, style)(f"**{text}**")

    if score is not None:
        st.metric("Overall Score", f"{score:.0%}")

    if reason:
        st.markdown(f"**Reason:** {reason}")

    st.page_link(
        "pages/4_verification_report.py",
        label="View Full Report →",
        use_container_width=False,
    )
    st.session_state["selected_app_id"] = app_id

# ── Auto-refresh ──────────────────────────────────────────────────

if auto_refresh and stage not in ("COMPLETE", "FAILED"):
    time.sleep(5)
    st.rerun()
