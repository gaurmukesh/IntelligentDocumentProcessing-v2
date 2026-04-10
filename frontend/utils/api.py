"""
API helpers — thin wrappers around requests.

Spring Boot ERP : http://localhost:8080
FastAPI AI svc  : http://localhost:8000
"""

import mimetypes
import requests

_MIME_MAP = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}

ERP_URL = "http://localhost:8080"
AI_URL = "http://localhost:8000"

TIMEOUT = 15


# ── Spring Boot ───────────────────────────────────────────────────

def create_student(payload: dict) -> dict:
    r = requests.post(f"{ERP_URL}/api/students", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_students() -> list:
    r = requests.get(f"{ERP_URL}/api/students", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def create_application(student_id: str) -> dict:
    r = requests.post(f"{ERP_URL}/api/applications",
                      json={"studentId": student_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_applications(status: str | None = None) -> list:
    params = {"status": status} if status else {}
    r = requests.get(f"{ERP_URL}/api/applications", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_application(app_id: str) -> dict:
    r = requests.get(f"{ERP_URL}/api/applications/{app_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def trigger_verification(app_id: str) -> bool:
    r = requests.post(f"{ERP_URL}/api/applications/{app_id}/trigger-verification",
                      timeout=TIMEOUT)
    return r.status_code in (200, 202)


# ── FastAPI ───────────────────────────────────────────────────────

def upload_document(app_id: str, doc_type: str, file_bytes: bytes, file_name: str) -> dict:
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    mime_type = _MIME_MAP.get(ext, "application/octet-stream")
    files = {"file": (file_name, file_bytes, mime_type)}
    data = {"application_id": app_id, "doc_type": doc_type}
    r = requests.post(f"{AI_URL}/documents/upload", files=files, data=data, timeout=30)
    r.raise_for_status()
    return r.json()


def get_pipeline_status(app_id: str) -> dict:
    r = requests.get(f"{AI_URL}/applications/{app_id}/pipeline-status", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_verification_report(app_id: str) -> dict:
    r = requests.get(f"{AI_URL}/verify/{app_id}/report", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def health_check() -> dict:
    """Check if FastAPI is reachable."""
    try:
        r = requests.get(f"{AI_URL}/health", timeout=5)
        return {"ok": r.status_code == 200}
    except Exception:
        return {"ok": False}
