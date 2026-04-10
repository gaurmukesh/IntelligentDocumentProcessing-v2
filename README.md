# Intelligent Document Processing (IDP)

Automated verification of student admission documents using AI-powered OCR, cross-document validation, and RAG-based eligibility checks.

---

## What This System Does

Automates the verification of student admission documents — 10th marksheet, 12th marksheet, and Aadhar card — for an Education ERP. It extracts data using GPT-4o Vision, validates consistency across documents, checks eligibility rules, and returns a final decision (APPROVED / REVIEW_REQUIRED / REJECTED).

---

## Architecture

```
┌─────────────────┐     Upload      ┌──────────────────────┐
│  Streamlit UI   │ ──────────────► │  FastAPI AI Service  │
│  (Frontend)     │                 │  (Python · Port 8000)│
│  Port: 8501     │ ◄────────────── │                      │
└─────────────────┘   Status/Report └──────┬───────────────┘
                                           │  Kafka Message
                                           ▼
                               ┌──────────────────────┐
                               │   Kafka Broker       │
                               │   (KRaft · Port 9092)│
                               └──────────┬───────────┘
                                          │
                                          ▼
                               ┌──────────────────────┐
                               │  GPT-4o Vision (OCR) │
                               │  OpenAI API          │
                               └──────────────────────┘

┌──────────────────────────────────────────────────────┐
│  Spring Boot ERP  (Java · Port 8080)                 │
│  Students · Applications · Verification Callback     │
└──────────────────────────────────────────────────────┘
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
| PDF Rendering | PyMuPDF — converts PDF pages to PNG at 216 DPI |
| RAG | LangChain · OpenAI text-embedding-3-small · Qdrant |
| Name Matching | thefuzz (Levenshtein distance) |

---

## Prerequisites

- Python 3.11+
- Java 17+
- Docker & Docker Compose
- OpenAI API Key

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/gaurmukesh/IntelligentDocumentProcessing.git
cd IntelligentDocumentProcessing
```

### 2. Configure environment variables

```bash
cp backend-fastapi/.env.example backend-fastapi/.env
```

Edit `backend-fastapi/.env` and add your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

### 3. Install Python dependencies

```bash
cd backend-fastapi
pip install -r requirements.txt
cd ../frontend
pip install -r requirements.txt
```

### 4. Run the system

Open 5 terminals:

```bash
# Terminal 1 — Kafka
docker compose up -d

# Terminal 2 — FastAPI AI Service
cd backend-fastapi
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Kafka Consumer
cd backend-fastapi
python -m app.services.kafka_consumer

# Terminal 4 — Spring Boot ERP
cd backend-springboot
./mvnw spring-boot:run

# Terminal 5 — Streamlit Frontend
cd frontend
streamlit run app.py
```

### 5. Ingest knowledge base (one-time)

```bash
curl -X POST http://localhost:8000/verify/knowledge-base/ingest
```

### 6. Open the app

Navigate to `http://localhost:8501` in your browser.

---

## How It Works

### End-to-End Flow

1. **Create Student & Application** — Register a student in the Spring Boot ERP
2. **Upload Documents** — Upload 10th marksheet, 12th marksheet, and Aadhar card via Streamlit
3. **AI Extraction (async)** — Kafka consumer picks up upload events; GPT-4o Vision extracts structured data from each document
4. **Trigger Verification** — Admin triggers verification; FastAPI runs validation in the background
5. **Validation Engine** — Runs field checks, cross-document checks, eligibility checks, and RAG-based rules
6. **Decision & Report** — Result is sent back to Spring Boot ERP; admin views the full report in Streamlit

### Decision Logic

| Outcome | Condition |
|---------|-----------|
| APPROVED | All required fields present, DOB matches, names match (≥85%), percentages meet thresholds, results are PASS |
| REVIEW_REQUIRED | Warnings present (low confidence, uncertain RAG result) but no critical failures |
| REJECTED | Missing required fields, DOB mismatch, name match <85%, or result = FAIL |

---

## Document Types Supported

| Document | Key Fields Extracted | Cross-Checks |
|----------|---------------------|--------------|
| 10th Marksheet | Name, DOB, Board, School, Roll No, Subjects, %, Result | Name ↔ 12th ↔ Aadhar; DOB ↔ Aadhar |
| 12th Marksheet | Name, Board, Stream, School, Roll No, Subjects, %, Result | Name ↔ 10th ↔ Aadhar |
| Aadhar Card | Name, DOB, Gender, Last-4 digits, Address | Name ↔ 10th ↔ 12th; DOB ↔ 10th |

---

## API Reference

The FastAPI service exposes a Swagger UI at `http://localhost:8000/docs`.

Key endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload a document for an application |
| GET | `/documents/{doc_id}` | Get document status and extracted data |
| POST | `/verify/{application_id}` | Trigger verification for an application |
| GET | `/verify/{application_id}/report` | Get the full verification report |
| GET | `/applications/{id}` | Get application details |
| GET | `/health` | Health check |

---

## Sample Verification Report

```json
{
  "status": "APPROVED",
  "overall_score": 0.91,
  "decision_reason": "All critical checks passed",
  "validation": {
    "checks": [
      { "check_name": "cross_doc_name_match",       "status": "PASS", "detail": "100% match across all documents" },
      { "check_name": "cross_doc_dob_match",         "status": "PASS", "detail": "20/01/2004 matches across documents" },
      { "check_name": "10th_percentage_eligibility", "status": "PASS", "detail": "79.2% meets minimum 35%" },
      { "check_name": "12th_percentage_eligibility", "status": "PASS", "detail": "72.6% meets minimum 45%" },
      { "check_name": "rag_eligibility_check",       "status": "PASS", "detail": "Student meets General Admission criteria" }
    ]
  }
}
```

---

## Project Structure

```
IntelligentDocumentProcessing/
├── backend-fastapi/          # Python FastAPI AI service
│   ├── app/
│   │   ├── core/             # Config, settings
│   │   ├── models/           # Database models, schemas
│   │   ├── routers/          # API routes (documents, verify, applications)
│   │   └── services/         # AI extraction, validation, Kafka, RAG
│   ├── data/                 # SQLite DB and uploaded files
│   ├── tests/                # Pytest test suite
│   └── requirements.txt
├── backend-springboot/       # Java Spring Boot ERP
│   └── src/main/java/com/idp/erp/
│       ├── controller/       # REST controllers
│       ├── service/          # Business logic
│       ├── entity/           # JPA entities
│       └── client/           # WebClient for FastAPI
├── frontend/                 # Streamlit UI
│   ├── app.py                # Entry point
│   ├── pages/                # Multi-page app
│   └── utils/                # API client helpers
├── data/knowledge_base/      # RAG eligibility rules
└── docker-compose.yml        # Kafka setup
```

---

## License

MIT
