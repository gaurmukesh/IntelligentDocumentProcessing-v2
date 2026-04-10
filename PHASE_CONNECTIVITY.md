# IDP — How Each Phase Connects to the Next

This document explains the exact API calls, data hand-offs, and code entry points that link each phase together.

---

## Big Picture — Who Talks to Whom

```
Streamlit UI
    │
    ├──── HTTP ────────────────────► Spring Boot  (port 8080)
    │                                     │
    │                                     │  HTTP (WebClient)
    │                                     ▼
    ├──── HTTP ────────────────────► FastAPI      (port 8000)
                                          │
                                          │  Kafka message (produce)
                                          ▼
                                     Kafka Broker  (port 9092)
                                          │
                                          │  Kafka message (consume)
                                          ▼
                                     Kafka Consumer process
                                          │
                                          │  OpenAI API call
                                          ▼
                                     GPT-4o Vision
                                          │
                                          │  Result saved to SQLite
                                          ▼
                                     FastAPI (callback)
                                          │
                                          │  HTTP POST (httpx)
                                          ▼
                                     Spring Boot (callback receiver)
```

---

## Phase 1 → Phase 2: Setup connects to Upload

### What happens
After a student and application are created in Spring Boot, the **application_id** (UUID) is the key that links everything. It travels across all systems.

### Call chain

```
Streamlit  →  Spring Boot  →  Streamlit returns app_id  →  user uploads docs
```

**Step 1 — Create Student**
```
Streamlit (1_new_application.py)
    calls: api.create_student(payload)
    ↓
POST http://localhost:8080/api/students
    Body: { "name": "...", "email": "...", "phone": "...", "dateOfBirth": "..." }
    ↓
Spring Boot: StudentController.create()
    → studentService.create(request)
    → studentRepository.save(student)
    Returns: { "id": "uuid", "name": "...", ... }
```

**Step 2 — Create Application**
```
Streamlit
    calls: api.create_application(student_id)
    ↓
POST http://localhost:8080/api/applications
    Body: { "studentId": "uuid" }
    ↓
Spring Boot: ApplicationController.create()
    → applicationService.create(request)
    → applicationRepository.save(application)   ← status = PENDING
    Returns: { "id": "app-uuid", "studentId": "...", "status": "PENDING" }
```

The **app-uuid** returned here is stored in Streamlit's session state and used in every subsequent call.

---

## Phase 2 → Phase 3: Upload triggers Extraction

### What happens
Streamlit sends the file to FastAPI. FastAPI saves it and drops a Kafka message. The consumer (separate process) picks it up and calls GPT-4o.

### Call chain

```
Streamlit  →  FastAPI (upload)  →  Kafka produce  →  Kafka Consumer  →  GPT-4o  →  SQLite
```

**Step 1 — File Upload**
```
Streamlit (1_new_application.py)
    calls: api.upload_document(app_id, doc_type, file_bytes, file_name)
    ↓
POST http://localhost:8000/documents/upload
    multipart/form-data:
        file:           (filename, bytes, "image/png" | "application/pdf")
        application_id: "app-uuid"
        doc_type:       "MARKSHEET_10TH" | "MARKSHEET_12TH" | "AADHAR"
    ↓
FastAPI: documents.py → upload_document()
    1. Saves file to disk:
           uploads/{application_id}/{doc_type}.{ext}
    2. Creates Document row in SQLite:
           id, application_id, doc_type, file_path, status=PENDING
    3. Publishes Kafka message:
           topic: "document-extraction"
           payload: {
               "document_id":    "doc-uuid",
               "application_id": "app-uuid",
               "doc_type":       "MARKSHEET_10TH",
               "file_path":      "uploads/app-uuid/MARKSHEET_10TH.pdf"
           }
    Returns: { "id": "doc-uuid", "status": "PENDING" }
```

**Step 2 — Kafka Consumer picks up the message**
```
kafka_consumer.py: run_consumer()
    KafkaConsumer.poll(timeout_ms=1000)
    ↓
    for each message:
        asyncio.run(process_message(msg.value))
        consumer.commit()          ← only after success (at-least-once delivery)
    ↓
process_message(message):
    1. Fetches Document from SQLite
    2. Sets status → EXTRACTING
    3. Calls: extract_document(file_path, doc_type)
              ↓
              extractor.py → file_to_base64(file_path)
                  PDF:   PyMuPDF → first page → PNG (216 DPI) → base64
                  Image: read bytes → base64
              ↓
              _call_vision(system_prompt, user_prompt, image_b64, media_type)
                  POST https://api.openai.com/v1/chat/completions
                  model: gpt-4o
                  messages: [ system, { text + image_url (base64 PNG) } ]
                  response_format: { type: "json_object" }
                  ↓
                  Returns structured JSON with confidence scores
    4. Saves ExtractionResult to SQLite
    5. Sets Document status → EXTRACTED  (or FAILED on error)
```

---

## Phase 3 → Phase 4: Extraction enables Verification Trigger

### What happens
Once all documents are EXTRACTED, the admin clicks "Trigger Verification" in Streamlit. This goes to Spring Boot first, which then calls FastAPI.

### Why it goes through Spring Boot first
Spring Boot is the ERP — it owns the application lifecycle. It must set the status to `UNDER_REVIEW` before delegating to FastAPI.

### Call chain

```
Streamlit  →  Spring Boot (trigger)  →  FastAPI (trigger)  →  Background task queued
```

**Step 1 — Streamlit triggers via Spring Boot**
```
Streamlit (2_applications.py or 3_pipeline_status.py)
    calls: api.trigger_verification(app_id)
    ↓
POST http://localhost:8080/api/applications/{app_id}/trigger-verification
    ↓
Spring Boot: ApplicationController.triggerVerification()
    → verificationService.triggerVerification(applicationId)
        1. Fetches Application from H2 DB
        2. Sets status → UNDER_REVIEW
        3. Saves to DB
        4. Calls FastAPI via WebClient:
               aiServiceClient.triggerVerification(applicationId)
               ↓
               POST http://localhost:8000/verify/{applicationId}
    Returns: 202 Accepted
```

**Step 2 — FastAPI queues the validation background task**
```
FastAPI: verify.py → trigger_verification()
    1. Checks documents exist for this application_id
    2. Queues background task:
           background_tasks.add_task(_run_validation_task, application_id)
    Returns: { "message": "Validation triggered", "application_id": "..." }
    ↓
    (response sent immediately — validation runs async)
```

---

## Phase 4 → Phase 5: Background Task runs Validation

### What happens
`_run_validation_task` runs after the HTTP response is already sent. It reads from SQLite, runs all checks, and saves the result.

### Call chain

```
FastAPI background task  →  SQLite (read extractions)  →  validator.py  →  RAG check  →  SQLite (save result)
```

```
_run_validation_task(application_id):
    │
    ├── 1. Read ExtractionResult rows from SQLite
    │         WHERE application_id = ?
    │         → extraction_rows[]
    │
    ├── 2. Check all Documents are EXTRACTED (not PENDING/EXTRACTING)
    │         If any still pending → return early (will be re-triggered)
    │
    ├── 3. Build extractions dict:
    │         { DocumentType → parsed JSON dict }
    │         { DocumentType → confidence_score }
    │
    ├── 4. validator.py → run_validation(extractions, doc_confidences)
    │         │
    │         ├── validate_required_fields()
    │         │       For each doc type, checks required fields are not null
    │         │       MARKSHEET_10TH: student_name, date_of_birth, board, exam_year, percentage, result
    │         │       MARKSHEET_12TH: student_name, date_of_birth*, board, stream, exam_year, percentage, result
    │         │       AADHAR:         full_name, date_of_birth, gender, aadhar_last4
    │         │
    │         ├── validate_name_match()
    │         │       Compares names across documents using thefuzz.token_sort_ratio()
    │         │       Threshold: 85 → PASS, 70–84 → WARNING, <70 → FAIL
    │         │
    │         ├── validate_dob_match()
    │         │       Normalises DOB strings to DD/MM/YYYY
    │         │       Exact match required across all docs that have DOB
    │         │
    │         ├── validate_percentage_eligibility()
    │         │       10th: ≥ 35%  →  PASS/FAIL
    │         │       12th: ≥ 45%  →  PASS/FAIL/WARNING (if percentage missing)
    │         │
    │         └── Returns: { checks[], overall_score, decision, decision_reason }
    │
    ├── 5. RAG Eligibility Check (if Qdrant knowledge base populated)
    │         rag.py → check_eligibility(course, pct_10th, pct_12th, stream, result_12th)
    │             │
    │             ├── Embed query using text-embedding-3-small
    │             ├── Qdrant similarity search → top-k relevant rules
    │             └── GPT-4 reasons over rules → { eligible, reason, confidence }
    │         Appended as "rag_eligibility_check" to checks[]
    │
    └── 6. Save ValidationResult to SQLite
              application_id, checks (JSON), overall_score, decision, decision_reason
```

---

## Phase 5 → Phase 6: Validation notifies Spring Boot

### What happens
After saving the result, FastAPI POSTs a callback to Spring Boot. Spring Boot updates the application status and stores the decision.

### Call chain

```
FastAPI (httpx POST)  →  Spring Boot callback  →  H2 DB updated
```

```
FastAPI: verify.py → _notify_erp(application_id, validation_output)
    │
    POST http://localhost:8080/api/applications/{application_id}/verification-result
    Body: {
        "decision":        "APPROVED" | "REJECTED" | "MANUAL_REVIEW",
        "overall_score":   0.91,
        "decision_reason": "All critical checks passed"
    }
    (using httpx.AsyncClient, timeout=10s, best-effort — failure logged not raised)
    ↓
Spring Boot: ApplicationController.verificationResult()
    → verificationService.applyVerificationResult(applicationId, callback)
        1. Fetches Application from H2 DB
        2. Maps decision string → VerificationDecision enum:
               "APPROVED"      → VerificationDecision.APPROVED
               "REJECTED"      → VerificationDecision.REJECTED
               "MANUAL_REVIEW" → VerificationDecision.MANUAL_REVIEW
        3. Sets:
               app.verificationDecision = decision
               app.verificationScore    = overall_score
               app.decisionReason       = decision_reason
        4. Maps decision → ApplicationStatus:
               APPROVED      → COMPLETED
               REJECTED      → REJECTED
               MANUAL_REVIEW → UNDER_REVIEW
        5. Saves to H2 DB
    Returns: 200 OK
```

---

## Phase 6 → UI: Streamlit reads the result

### What happens
Streamlit polls FastAPI's pipeline-status endpoint to show live progress, then fetches the full report.

### Call chain

```
Streamlit  →  FastAPI (pipeline-status)   [polling every few seconds]
Streamlit  →  FastAPI (report)            [once COMPLETE]
```

**Polling pipeline status**
```
Streamlit (3_pipeline_status.py)
    calls: api.get_pipeline_status(app_id)
    ↓
GET http://localhost:8000/applications/{app_id}/pipeline-status
    ↓
FastAPI: applications.py → get_pipeline_status()
    Reads Document rows + ExtractionResult rows + ValidationResult from SQLite
    Derives pipeline_stage:
        any FAILED doc           → "FAILED"
        any EXTRACTING doc       → "EXTRACTING"
        any PENDING doc          → "UPLOADING"
        ValidationResult exists  → "COMPLETE"
        else                     → "VALIDATING"
    Returns: { pipeline_stage, documents[], verification: { decision, score } }
```

**Fetching the full report**
```
Streamlit (4_verification_report.py)
    calls: api.get_verification_report(app_id)
    ↓
GET http://localhost:8000/verify/{app_id}/report
    ↓
FastAPI: verify.py → get_verification_report()
    Reads ValidationResult + ExtractionResult[] from SQLite
    Returns: {
        application_id, status, overall_score, decision_reason,
        documents: [ { doc_type, extracted_data, confidence_score } ],
        validation: { checks[], overall_score, decision }
    }
```

---

## Complete Data Flow — One Document's Journey

```
1.  Admin uploads "10th_marksheet.pdf"
        Streamlit → POST /documents/upload (FastAPI)
        SQLite: Document { id="doc-1", status=PENDING }
        Kafka message → topic: document-extraction

2.  Kafka consumer picks up message
        SQLite: Document { status=EXTRACTING }
        PyMuPDF: PDF page 0 → PNG (216 DPI)
        OpenAI API: PNG → JSON { student_name, dob, marks... }
        SQLite: ExtractionResult { doc_type=MARKSHEET_10TH, confidence=0.84 }
        SQLite: Document { status=EXTRACTED }

3.  Admin uploads remaining docs (12th, Aadhar) — same flow

4.  Admin clicks "Trigger Verification"
        Streamlit → POST /api/applications/app-1/trigger-verification (Spring Boot)
        Spring Boot H2: Application { status=UNDER_REVIEW }
        Spring Boot → POST /verify/app-1 (FastAPI)
        FastAPI: background task queued

5.  Background task runs
        Reads 3 ExtractionResults from SQLite
        Runs 22 validation checks
        Runs RAG eligibility check
        SQLite: ValidationResult { decision=APPROVED, score=0.91 }
        FastAPI → POST /api/applications/app-1/verification-result (Spring Boot)
        Spring Boot H2: Application { status=COMPLETED, verificationDecision=APPROVED }

6.  Streamlit polls pipeline-status → sees "COMPLETE"
        Streamlit → GET /verify/app-1/report (FastAPI)
        Displays full report with all checks and extracted data
```

---

## Key IDs That Link Everything

| ID | Created by | Used by |
|----|-----------|---------|
| `student_id` (UUID) | Spring Boot on student create | Spring Boot to link application → student |
| `application_id` (UUID) | Spring Boot on application create | **Everything** — travels across all services |
| `document_id` (UUID) | FastAPI on file upload | Kafka message, ExtractionResult, status updates |

The `application_id` is the single shared key across Spring Boot (H2), FastAPI (SQLite), Kafka messages, and Streamlit session state.

---

## Error Handling at Each Boundary

| Boundary | Error handling |
|----------|---------------|
| Streamlit → Spring Boot | `requests.raise_for_status()` — shows error in UI |
| Streamlit → FastAPI | `requests.raise_for_status()` — shows error in UI |
| FastAPI → Kafka | `KafkaProducerError` raised and returned as 500 |
| Kafka Consumer → OpenAI | Exception caught → ExtractionResult saved with `error_message`, Document status = FAILED |
| FastAPI → Spring Boot callback | `httpx` exception caught and logged — non-blocking (best-effort) |
| Spring Boot → FastAPI (WebClient) | Returns `false` if non-2xx — logged as warning, does not block ERP |
