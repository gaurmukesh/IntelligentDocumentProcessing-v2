"""
Page 1 — New Application

Step 1: Enter student details  →  create student in Spring Boot
Step 2: Upload 3 documents     →  send to FastAPI
Step 3: Trigger verification   →  Spring Boot calls FastAPI pipeline
"""

import streamlit as st
import datetime
from utils.api import create_student, create_application, upload_document, trigger_verification

st.set_page_config(page_title="New Application", page_icon="📝", layout="wide")
st.title("New Application")

COURSES = ["B.Tech", "B.Sc", "B.Com", "BBA", "BA", "MBA", "M.Tech"]

DOC_TYPES = {
    "MARKSHEET_10TH": "10th Grade Marksheet",
    "MARKSHEET_12TH": "12th Grade Marksheet",
    "AADHAR":         "Aadhar Card (Front Side)",
}

# ── Session state ─────────────────────────────────────────────────

if "step" not in st.session_state:
    st.session_state.step = 1
if "student" not in st.session_state:
    st.session_state.student = None
if "application" not in st.session_state:
    st.session_state.application = None
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = {}

# ── Progress indicator ────────────────────────────────────────────

steps = ["Student Details", "Upload Documents", "Submit & Verify"]
cols = st.columns(3)
for i, (col, label) in enumerate(zip(cols, steps), 1):
    with col:
        if i < st.session_state.step:
            st.success(f"✅ Step {i}: {label}")
        elif i == st.session_state.step:
            st.info(f"▶ Step {i}: {label}")
        else:
            st.markdown(f"⬜ Step {i}: {label}")

st.divider()

# ── Step 1: Student Details ───────────────────────────────────────

if st.session_state.step == 1:
    st.subheader("Student Details")

    with st.form("student_form"):
        col1, col2 = st.columns(2)

        with col1:
            full_name = st.text_input("Full Name *", placeholder="e.g. Rahul Sharma")
            email = st.text_input("Email *", placeholder="rahul@example.com")
            phone = st.text_input("Phone *", placeholder="9876543210")

        with col2:
            dob = st.date_input(
                "Date of Birth *",
                value=datetime.date(2003, 1, 1),
                min_value=datetime.date(1980, 1, 1),
                max_value=datetime.date(2010, 12, 31),
            )
            course = st.selectbox("Course Applied *", COURSES)

        submitted = st.form_submit_button("Save & Continue", type="primary", use_container_width=True)

        if submitted:
            if not all([full_name, email, phone, course]):
                st.error("Please fill in all required fields.")
            else:
                with st.spinner("Creating student record..."):
                    try:
                        student = create_student({
                            "fullName": full_name,
                            "email": email,
                            "phone": phone,
                            "dateOfBirth": dob.isoformat(),
                            "courseApplied": course,
                        })
                        application = create_application(student["id"])
                        st.session_state.student = student
                        st.session_state.application = application
                        st.session_state.step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create student: {e}")

# ── Step 2: Upload Documents ──────────────────────────────────────

elif st.session_state.step == 2:
    app = st.session_state.application
    student = st.session_state.student

    st.subheader("Upload Documents")
    st.info(
        f"**Application ID:** `{app['id']}`  |  "
        f"**Student:** {student['fullName']}  |  "
        f"**Course:** {student['courseApplied']}"
    )

    all_uploaded = True

    for doc_type, label in DOC_TYPES.items():
        st.markdown(f"**{label}**")
        uploaded = st.file_uploader(
            f"Choose file for {label}",
            type=["pdf", "jpg", "jpeg", "png"],
            key=f"file_{doc_type}",
        )

        if uploaded:
            if doc_type not in st.session_state.uploaded_docs:
                with st.spinner(f"Uploading {label}..."):
                    try:
                        result = upload_document(
                            app["id"],
                            doc_type,
                            uploaded.read(),
                            uploaded.name,
                        )
                        st.session_state.uploaded_docs[doc_type] = result
                        st.success(f"Uploaded: {uploaded.name}")
                    except Exception as e:
                        st.error(f"Upload failed: {e}")
                        all_uploaded = False
            else:
                st.success(f"Already uploaded: {uploaded.name}")
        else:
            all_uploaded = False

        st.markdown("---")

    uploaded_count = len(st.session_state.uploaded_docs)
    st.markdown(f"**{uploaded_count} / {len(DOC_TYPES)} documents uploaded**")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 1
            st.session_state.uploaded_docs = {}
            st.rerun()
    with col2:
        proceed = st.button(
            "Continue →",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_count < len(DOC_TYPES)),
        )
        if proceed:
            st.session_state.step = 3
            st.rerun()

# ── Step 3: Submit & Verify ───────────────────────────────────────

elif st.session_state.step == 3:
    app = st.session_state.application
    student = st.session_state.student

    st.subheader("Submit for Verification")

    st.success(f"**{len(DOC_TYPES)} documents uploaded successfully**")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Student**")
        st.markdown(f"Name: {student['fullName']}")
        st.markdown(f"Email: {student['email']}")
        st.markdown(f"Course: {student['courseApplied']}")

    with col2:
        st.markdown("**Application**")
        st.markdown(f"ID: `{app['id']}`")
        st.markdown(f"Status: {app['status']}")
        for doc_type, label in DOC_TYPES.items():
            doc = st.session_state.uploaded_docs.get(doc_type)
            if doc:
                st.markdown(f"✅ {label}")

    st.divider()

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Start AI Verification", type="primary", use_container_width=True):
            with st.spinner("Triggering verification pipeline..."):
                try:
                    ok = trigger_verification(app["id"])
                    if ok:
                        st.success(
                            f"Verification started! Application ID: `{app['id']}`\n\n"
                            "Go to **Pipeline Status** to track progress."
                        )
                        st.session_state.step = 1
                        st.session_state.student = None
                        st.session_state.application = None
                        st.session_state.uploaded_docs = {}
                    else:
                        st.error("Failed to trigger verification. Please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")
