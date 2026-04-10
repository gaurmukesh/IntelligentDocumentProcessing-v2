# Intelligent Document Processing (IDP) — End-to-End Application Flow

## What This System Does

Automates the verification of student admission documents (10th marksheet, 12th marksheet, Aadhar card) for an Education ERP using AI-powered OCR, cross-document validation, and RAG-based eligibility checks.

---

## Architecture Overview

```
┌─────────────────┐     Upload      ┌──────────────────────┐
│  Streamlit UI   │ ──────────────► │  FastAPI AI Service  │
│  (Frontend)     │                 │  (Python · Port 8000)│
│  Port: 8501     │ ◄────────────── │                      │
└─────────────────┘   Status/Report └──────┬───────────────┘
                                           │  Kafka Message
         ┌─────────────────────────────────┼──────────────────────┐
         │                                 ▼                      │
         │                     ┌──────────────────────┐           │
         │  Spring Boot ERP    │   Kafka Broker       │           │
         │  (Java · Port 8080) │   (KRaft · Port 9092)│           │
         │                     └──────────┬───────────┘           │
         │                                │                       │
         │                                ▼                       │
         │                     ┌──────────────────────┐           │
         │                     │   Kafka Consumer     │           │
         │                     │   (FastAPI process)  │           │
         │                     └──────────┬───────────┘           │
         │                                │                       │
         │                                ▼                       │
         │                     ┌──────────────────────┐           │
         │                     │  GPT-4o Vision (OCR) │           │
         │                     │  OpenAI API          │           │
         │                     └──────────────────────┘           │
         │                                                        │
         │  Callback (verification result)                        │
         │ ◄──────────────────────────────────────────────────── │
         └────────────────────────────────────────────────────────┘
```

### Storage
| Store | Technology | Purpose |
|-------|-----------|---------|
| Document metadata | SQLite (FastAPI) | Documents, extraction results, validation results |
| ERP data | H2 in-memory (Spring Boot) | Students, applications, statuses |
| Vector store | Qdrant (in-memory) | RAG knowledge base for eligibility rules |
| File storage | Local disk | Uploaded PDF/image files |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Python · Streamlit |
| AI Service | Python · FastAPI · SQLAlchemy (async) · aiosqlite |
| ERP Backend | Java · Spring Boot · Spring Data JPA · WebFlux WebClient |
| Message Queue | Apache Kafka (KRaft mode — no Zookeeper) |
| OCR / Extraction | OpenAI GPT-4o Vision API |
| PDF Rendering | PyMuPDF (fitz) — converts PDF pages to PNG at 216 DPI |
| RAG | LangChain · OpenAI text-embedding-3-small · Qdrant |
| Name Matching | thefuzz (Levenshtein distance) |

---

## End-to-End Flow

### Phase 1 — Student & Application Setup

```
Admin (Streamlit)
    │
    ├── 1. Create Student
    │       POST /api/students  →  Spring Boot ERP
    │       Stores: name, email, phone, date_of_birth
    │
    └── 2. Create Application
            POST /api/applications  →  Spring Boot ERP
            Stores: studentId, status = PENDING
```

### Phase 2 — Document Upload

```
Admin uploads PDF/image for each document type
    │
    ├── Streamlit calls FastAPI:
    │       POST /documents/upload
    │       Body: file (multipart), application_id, doc_type
    │
    ├── FastAPI:
    │   ├── Saves file to disk:  uploads/{application_id}/{doc_type}.pdf
    │   ├── Creates Document record in SQLite  (status = PENDING)
    │   └── Publishes Kafka message:
    │           topic: document-processing
    │           payload: { document_id, application_id, doc_type, file_path }
    │
    └── Returns: { document_id, status: "PENDING" }
```

### Phase 3 — AI Extraction (Async via Kafka)

```
Kafka Consumer picks up message
    │
    ├── Updates Document status → EXTRACTING
    │
    ├── PDF Handling (PyMuPDF):
    │       PDF → first page → PNG image (216 DPI / 3× zoom)
    │       PNG → base64 encoded string
    │
    ├── GPT-4o Vision API call:
    │       System prompt: expert extractor for doc type
    │       User prompt:   structured JSON schema to fill
    │       Image:         base64 PNG
    │       response_format: { type: "json_object" }
    │
    ├── Extracted fields per document:
    │
    │   MARKSHEET_10TH:
    │       student_name, date_of_birth, school_name, board,
    │       exam_year, roll_number, subjects[], total_marks,
    │       percentage, result, grade
    │
    │   MARKSHEET_12TH:
    │       student_name, date_of_birth*, school_name, board,
    │       stream (inferred from subjects if not printed),
    │       exam_year, roll_number, subjects[], total_marks
    │       (calculated from theory subjects), percentage, result
    │       (* CBSE 12th marksheets may not print DOB)
    │
    │   AADHAR:
    │       full_name, date_of_birth, gender,
    │       aadhar_last4 (last 4 digits only — rest masked),
    │       address, is_front_side
    │
    ├── Each field has a confidence score (0.0–1.0)
    │
    ├── Saves ExtractionResult to SQLite
    └── Updates Document status → EXTRACTED (or FAILED)
```

### Phase 4 — Verification Trigger

```
Admin clicks "Trigger Verification" in Streamlit
    │
    ├── Streamlit → Spring Boot:
    │       POST /api/applications/{id}/trigger-verification
    │
    ├── Spring Boot:
    │   ├── Sets application status → UNDER_REVIEW
    │   └── Calls FastAPI:
    │           POST /verify/{application_id}
    │
    └── FastAPI queues background task: _run_validation_task
```

### Phase 5 — Validation Engine

```
_run_validation_task runs in background
    │
    ├── Waits until all documents are EXTRACTED (not PENDING/EXTRACTING)
    │
    ├── A. Per-Document Field Checks
    │       For each required field: checks value is not null
    │       Status: PASS / FAIL
    │       Confidence: from extraction step
    │
    ├── B. Cross-Document Checks
    │
    │   Name Match (fuzzy):
    │       10th name  ↔  12th name  ↔  Aadhar name
    │       Uses Levenshtein distance → score 0–100
    │       Threshold: 85% match required
    │       Status: PASS / WARNING / FAIL
    │
    │   DOB Match (exact after normalisation):
    │       10th DOB  ↔  Aadhar DOB
    │       Normalised to DD/MM/YYYY before comparing
    │       Status: PASS / FAIL
    │
    ├── C. Eligibility Checks
    │
    │   10th Percentage:   ≥ 35% required  →  PASS / FAIL
    │   12th Percentage:   ≥ 45% required  →  PASS / FAIL / WARNING
    │   12th Result:       must be PASS    →  PASS / FAIL
    │
    ├── D. RAG Eligibility Check (if knowledge base ingested)
    │
    │   Student profile:  pct_10th, pct_12th, stream, result
    │   Query vector store for matching eligibility rules
    │   GPT-4 reasons over retrieved rules → eligible: true/false
    │   Status: PASS / WARNING / FAIL
    │
    ├── Overall Score:
    │       Average confidence across all PASS checks
    │
    └── Decision:
            APPROVED       — all critical checks PASS
            REVIEW_REQUIRED — warnings present, no critical failures
            REJECTED       — one or more critical checks FAIL
```

### Phase 6 — Result Callback & Report

```
After validation completes:
    │
    ├── FastAPI saves ValidationResult to SQLite
    │
    ├── FastAPI → Spring Boot callback (best-effort):
    │       POST /api/applications/{id}/verification-result
    │       Body: { decision, overall_score, decision_reason }
    │
    ├── Spring Boot maps decision → ApplicationStatus:
    │       APPROVED        → APPROVED
    │       REVIEW_REQUIRED → PENDING_REVIEW
    │       REJECTED        → REJECTED
    │
    └── Admin views report in Streamlit:
            GET /verify/{application_id}/report
            Shows: decision, score, all check results, extracted data
```

---

## Decision Logic

```
Critical failures (→ REJECTED):
  • Any required field missing in any document
  • DOB mismatch across documents
  • 10th/12th result = FAIL
  • Name match below 85%

Warnings (→ REVIEW_REQUIRED if no critical failures):
  • Low confidence scores (< 0.7)
  • RAG eligibility uncertain
  • Optional field missing (e.g., grade)

All pass (→ APPROVED):
  • All required fields present
  • DOB matches across documents
  • Names match (≥ 85% fuzzy)
  • Percentages meet thresholds
  • Results are PASS
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Kafka for async processing | Document AI extraction takes 2–5s; async keeps upload API responsive |
| PyMuPDF for PDF→PNG | No system dependencies (unlike pdf2image + poppler); pure Python wheel |
| GPT-4o Vision | Best-in-class OCR for complex Indian marksheet layouts |
| 216 DPI rendering | 3× zoom reduces digit misreads (e.g., "1" vs "3" in months) |
| Aadhar last-4 only | Privacy by design — full number never stored |
| Fuzzy name matching | Handles case differences, initials, minor spelling variations |
| RAG for eligibility | Rules in knowledge base can be updated without code changes |
| Spring Boot callback | Decoupled — ERP doesn't poll; FastAPI pushes result when ready |

---

## Running the System

```bash
# Terminal 1 — Kafka
docker compose up -d

# Terminal 2 — FastAPI
cd backend-fastapi
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Kafka Consumer
cd backend-fastapi
source venv/bin/activate
python -m app.services.kafka_consumer

# Terminal 4 — Spring Boot
cd backend-springboot
./mvnw spring-boot:run

# Terminal 5 — Streamlit
cd frontend
streamlit run Home.py
```

One-time setup (after first start):
```bash
# Ingest knowledge base into Qdrant
curl -X POST http://localhost:8000/verify/knowledge-base/ingest
```

---

## Sample Verification Report

```json
{
  "status": "APPROVED",
  "overall_score": 0.91,
  "decision_reason": "All critical checks passed",
  "validation": {
    "checks": [
      { "check_name": "cross_doc_name_match",  "status": "PASS",    "detail": "100% match across all documents" },
      { "check_name": "cross_doc_dob_match",   "status": "PASS",    "detail": "20/01/2004 matches across documents" },
      { "check_name": "10th_percentage_eligibility", "status": "PASS", "detail": "79.2% meets minimum 35%" },
      { "check_name": "12th_percentage_eligibility", "status": "PASS", "detail": "72.6% meets minimum 45%" },
      { "check_name": "rag_eligibility_check", "status": "PASS",    "detail": "Student meets General Admission criteria" }
    ]
  }
}
```

---

## Document Types Supported

| Document | Key Fields Extracted | Cross-Checks |
|----------|---------------------|--------------|
| 10th Marksheet | Name, DOB, Board, School, Roll No, Subjects, %, Result | Name ↔ 12th ↔ Aadhar; DOB ↔ Aadhar |
| 12th Marksheet | Name, Board, Stream, School, Roll No, Subjects, %, Result | Name ↔ 10th ↔ Aadhar |
| Aadhar Card | Name, DOB, Gender, Last-4 digits, Address | Name ↔ 10th ↔ 12th; DOB ↔ 10th |
