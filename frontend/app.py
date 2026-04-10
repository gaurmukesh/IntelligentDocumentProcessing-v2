"""
IDP — Intelligent Document Processing
Streamlit multi-page app entry point.

Run with:
    cd frontend
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="IDP — Document Verification",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Intelligent Document Processing")
st.markdown("**Automated admission document verification powered by AI**")

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.info("**New Application**\n\nRegister a student and upload documents for verification.")

with col2:
    st.info("**Applications**\n\nView all applications and their current verification status.")

with col3:
    st.info("**Pipeline Status**\n\nTrack real-time progress of AI document processing.")

with col4:
    st.info("**Verification Report**\n\nView the full AI verification report with all checks.")

st.divider()

# Quick service health indicator
from utils.api import health_check
status = health_check()
if status["ok"]:
    st.success("AI Service (FastAPI) is online", icon="✅")
else:
    st.error("AI Service (FastAPI) is offline — start it with `uvicorn app.main:app`", icon="⚠️")
