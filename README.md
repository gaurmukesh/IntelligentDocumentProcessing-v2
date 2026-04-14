# Intelligent Document Processing (IDP)

Automated verification of student admission documents using AI-powered OCR, cross-document validation, and RAG-based eligibility checks — deployed on AWS Lightsail.

---

## What This System Does

Automates the verification of student admission documents — 10th marksheet, 12th marksheet, and Aadhar card — for an Education ERP. It extracts data using GPT-4o Vision, validates consistency across documents, checks eligibility rules, and returns a final decision (APPROVED / REVIEW_REQUIRED / REJECTED).

---

## Production Deployment (AWS Lightsail)

| Component | Service | Details |
|-----------|---------|---------|
| React Frontend | Lightsail Object Storage | Static website hosting (S3-compatible) |
| FastAPI AI Service | Lightsail Container Service | Docker container, auto-scaled |
| PostgreSQL Database | Lightsail Managed Database | postgres_14, micro_2_0 bundle |
| File Storage | Lightsail Object Storage | S3-compatible, boto3 integration |
| Apache Kafka | Lightsail Instance (Docker) | KRaft mode, port 9092 |
| Qdrant Vector Store | Lightsail Instance (Docker) | Server mode, port 6333 |
| Kafka Consumer | Lightsail Instance (systemd) | Auto-restart on crash/reboot |

**Region:** ap-south-1 (Mumbai)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Lightsail                            │
│                                                                 │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │  React Frontend │        │   FastAPI AI Service         │   │
│  │  (Object Storage│──────► │   (Container Service)        │   │
│  │   Static Site)  │        │   Port: 8000                 │   │
│  └─────────────────┘        └──────────┬───────────────────┘   │
│                                        │                        │
│                          ┌─────────────▼──────────────────┐    │
│                          │   Lightsail Managed PostgreSQL  │    │
│                          │   (postgres_14)                 │    │
│                          └────────────────────────────────┘    │
│                                        │                        │
│                          ┌─────────────▼──────────────────┐    │
│                          │   Lightsail Instance            │    │
│                          │   ┌─────────────────────────┐  │    │
│                          │   │  Kafka (Docker)          │  │    │
│                          │   │  Port: 9092              │  │    │
│                          │   └────────────┬────────────┘  │    │
│                          │                │               │    │
│                          │   ┌────────────▼────────────┐  │    │
│                          │   │  Kafka Consumer          │  │    │
│                          │   │  (systemd service)       │  │    │
│                          │   └────────────┬────────────┘  │    │
│                          │                │               │    │
│                          │   ┌────────────▼────────────┐  │    │
│                          │   │  GPT-4o Vision (OpenAI) │  │    │
│                          │   └─────────────────────────┘  │    │
│                          │                                 │    │
│                          │   ┌─────────────────────────┐  │    │
│                          │   │  Qdrant (Docker)         │  │    │
│                          │   │  Port: 6333              │  │    │
│                          │   └─────────────────────────┘  │    │
│                          └────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Lightsail Object Storage (S3-compatible)                │   │
│  │  - idp-uploads-swastik  (document files)                 │   │
│  │  - idp-frontend-swastik (React static files)             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  Spring Boot ERP  (Java · Port 8080)                 │
│  Students · Applications · Verification Callback     │
└──────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 · Vite · Tailwind CSS · React Router |
| AI Service | Python · FastAPI · SQLAlchemy (async) · asyncpg |
| ERP Backend | Java · Spring Boot · Spring Data JPA · WebFlux WebClient |
| Message Queue | Apache Kafka (KRaft mode — no Zookeeper) |
| OCR / Extraction | OpenAI GPT-4o Vision API |
| PDF Rendering | PyMuPDF — converts PDF pages to PNG at 216 DPI |
| RAG | LangChain · OpenAI text-embedding-3-small · Qdrant |
| Name Matching | thefuzz (Levenshtein distance) |
| File Storage | AWS S3-compatible (Lightsail Object Storage) · boto3 |
| Database | PostgreSQL 14 (production) |
| Infrastructure | AWS Lightsail (Container Service, Managed DB, Object Storage, Instance) |
| Container | Docker · docker-compose |
| Process Manager | systemd (Kafka consumer) |

---

## How It Works

### End-to-End Flow

1. **Create Student & Application** — Register a student in the Spring Boot ERP
2. **Upload Documents** — Upload 10th marksheet, 12th marksheet, and Aadhar card via the React frontend
3. **File Storage** — Documents are stored in Lightsail Object Storage (S3-compatible) via boto3
4. **AI Extraction (async)** — FastAPI publishes a Kafka message; the consumer picks it up and runs GPT-4o Vision OCR
5. **Trigger Verification** — Admin triggers verification; FastAPI runs validation in the background
6. **Validation Engine** — Runs field checks, cross-document checks, eligibility checks, and RAG-based rules
7. **Decision & Report** — Result is sent back to Spring Boot ERP; admin views the full report in the React frontend

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

## Project Structure

```
IntelligentDocumentProcessing/
├── backend-fastapi/              # Python FastAPI AI service
│   ├── app/
│   │   ├── core/                 # Config, settings (S3, Qdrant, DB, Kafka)
│   │   ├── models/               # Database models, Pydantic schemas
│   │   ├── routers/              # API routes (documents, verify, applications)
│   │   └── services/             # AI extraction, validation, Kafka, RAG, storage
│   │       └── storage.py        # S3 / local storage abstraction
│   ├── Dockerfile                # linux/amd64 production image
│   └── requirements.txt
├── backend-springboot/           # Java Spring Boot ERP
│   └── src/main/java/com/idp/erp/
│       ├── controller/           # REST controllers
│       ├── service/              # Business logic
│       ├── entity/               # JPA entities
│       └── client/               # WebClient for FastAPI
├── frontend-react/               # React 18 + Vite + Tailwind frontend
│   ├── src/
│   │   ├── pages/                # Home, NewApplication, Applications,
│   │   │                         # PipelineStatus, VerificationReport
│   │   ├── components/           # Layout, StatusBadge
│   │   └── api/                  # Axios API client
│   ├── vite.config.js
│   └── Dockerfile
├── deploy/                       # AWS Lightsail deployment scripts
│   ├── 1-setup-lightsail-instance.sh   # Install Docker on instance
│   ├── 2-create-lightsail-resources.sh # Create DB, buckets, container service
│   ├── 3-deploy-api.sh                 # Build & push FastAPI to container service
│   └── 4-deploy-frontend.sh            # Build React & sync to S3 bucket
├── docker-compose.yml            # Local development (Kafka, Qdrant)
├── docker-compose.prod.yml       # Local production simulation
├── nginx/nginx.conf              # Nginx config (self-hosted alternative)
├── data/knowledge_base/          # RAG eligibility rules
└── .env.prod.example             # Environment variable template
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Java 17+
- Node.js 18+
- Docker & Docker Compose
- OpenAI API Key

### 1. Clone the repository

```bash
git clone https://github.com/gaurmukesh/IntelligentDocumentProcessing-v2.git
cd IntelligentDocumentProcessing-v2
```

### 2. Configure environment variables

```bash
cp .env.prod.example backend-fastapi/.env
```

Edit `backend-fastapi/.env` and add your OpenAI API key and other settings.

### 3. Start infrastructure

```bash
docker compose up -d   # starts Kafka and Qdrant
```

### 4. Run the services

```bash
# Terminal 1 — FastAPI AI Service
cd backend-fastapi
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Kafka Consumer
cd backend-fastapi
python -m app.services.kafka_consumer

# Terminal 3 — Spring Boot ERP
cd backend-springboot
./mvnw spring-boot:run

# Terminal 4 — React Frontend
cd frontend-react
npm install && npm run dev
```

### 5. Ingest knowledge base (one-time)

```bash
curl -X POST http://localhost:8000/verify/knowledge-base/ingest
```

### 6. Open the app

Navigate to `http://localhost:3000` in your browser.

---

## Production Deployment

### Prerequisites

- AWS CLI configured (`aws configure`)
- Docker running locally
- `.env.prod` filled in (see `.env.prod.example`)

### Deploy steps

```bash
# Step 1: Create Lightsail resources (DB, buckets, container service)
chmod +x deploy/2-create-lightsail-resources.sh
./deploy/2-create-lightsail-resources.sh

# Step 2: Deploy FastAPI to Lightsail Container Service
chmod +x deploy/3-deploy-api.sh
./deploy/3-deploy-api.sh

# Step 3: Deploy React frontend to Lightsail Object Storage
chmod +x deploy/4-deploy-frontend.sh
./deploy/4-deploy-frontend.sh
```

---

## API Reference

The FastAPI service exposes a Swagger UI at `http://localhost:8000/docs` (or your container service URL).

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

## License

MIT
