"""
Page 2 — Applications List

Shows all applications in a table with status filter.
Click any row to navigate to its pipeline status or report.
"""

import streamlit as st
import pandas as pd
from utils.api import get_applications, trigger_verification

st.set_page_config(page_title="Applications", page_icon="📋", layout="wide")
st.title("Applications")

STATUS_COLOURS = {
    "DRAFT":        "⬜",
    "SUBMITTED":    "🔵",
    "UNDER_REVIEW": "🟡",
    "COMPLETED":    "🟢",
    "REJECTED":     "🔴",
}

DECISION_COLOURS = {
    "PENDING":       "⬜",
    "APPROVED":      "🟢",
    "REJECTED":      "🔴",
    "MANUAL_REVIEW": "🟡",
}

# ── Filters ───────────────────────────────────────────────────────

col1, col2 = st.columns([2, 6])
with col1:
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "DRAFT", "SUBMITTED", "UNDER_REVIEW", "COMPLETED", "REJECTED"],
    )

with col2:
    if st.button("Refresh", use_container_width=False):
        st.rerun()

# ── Fetch & display ───────────────────────────────────────────────

try:
    filter_val = None if status_filter == "All" else status_filter
    applications = get_applications(filter_val)
except Exception as e:
    st.error(f"Could not reach Spring Boot ERP: {e}")
    st.info("Make sure Spring Boot is running on port 8080.")
    st.stop()

if not applications:
    st.info("No applications found.")
    st.stop()

# Build display dataframe
rows = []
for app in applications:
    status_icon = STATUS_COLOURS.get(app.get("status", ""), "")
    decision_icon = DECISION_COLOURS.get(app.get("verificationDecision", "PENDING"), "")
    rows.append({
        "Application ID": app["id"],
        "Student": app.get("studentName", "—"),
        "Course": app.get("courseApplied", "—"),
        "Status": f"{status_icon} {app.get('status', '—')}",
        "Decision": f"{decision_icon} {app.get('verificationDecision', 'PENDING')}",
        "Score": f"{app.get('verificationScore', 0) or 0:.0%}" if app.get("verificationScore") else "—",
        "Created": app.get("createdAt", "")[:10] if app.get("createdAt") else "—",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown(f"**{len(applications)} application(s)** found")

st.divider()

# ── Quick actions ─────────────────────────────────────────────────

st.subheader("Quick Actions")
app_ids = [a["id"] for a in applications]
selected_id = st.selectbox("Select Application ID", app_ids, index=0)

if selected_id:
    selected = next((a for a in applications if a["id"] == selected_id), None)
    if selected:
        st.markdown(
            f"**Student:** {selected.get('studentName')}  |  "
            f"**Status:** {selected.get('status')}  |  "
            f"**Decision:** {selected.get('verificationDecision', 'PENDING')}"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Trigger Verification", use_container_width=True, type="primary"):
                with st.spinner("Triggering..."):
                    try:
                        ok = trigger_verification(selected_id)
                        if ok:
                            st.success("Verification triggered. Check Pipeline Status.")
                        else:
                            st.error("Failed to trigger verification.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with col2:
            st.page_link(
                "pages/3_pipeline_status.py",
                label="View Pipeline Status",
                use_container_width=True,
            )

        with col3:
            st.page_link(
                "pages/4_verification_report.py",
                label="View Report",
                use_container_width=True,
            )

        # Store selected ID in session for other pages
        st.session_state["selected_app_id"] = selected_id
