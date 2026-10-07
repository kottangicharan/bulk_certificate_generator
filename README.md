# Bulk Certificate Generator

A FastAPI backend that accepts bulk certificate-generation requests, produces PDF certificates from a predefined template, tracks job status, and lets clients download the results.

---

## Table of Contents

- [Setup](#setup)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [API Usage](#api-usage)
  - [Submit a Certificate Generation Request](#1-submit-a-certificate-generation-request)
  - [Check Job Status](#2-check-job-status)
  - [List All Jobs](#3-list-all-jobs)
  - [Download a Certificate](#4-download-a-certificate)
  - [Download All Certificates of a Job (ZIP)](#5-download-all-certificates-of-a-job-zip)
- [Design Decisions](#design-decisions)

---

## Setup

### Prerequisites

- Python 3.10+

### Install dependencies

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

No external services (Redis, PostgreSQL, etc.) are required — the app uses SQLite out of the box.

---

## Running the Application

```bash
uvicorn app.main:app --reload
```

The server starts at **http://localhost:8000**.

Interactive API documentation is available at:
- Swagger UI: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an isolated temporary SQLite database and a temporary certificates directory (via `pytest`'s `tmp_path`), so they do not interfere with production data.

---

## API Usage

### 1. Submit a Certificate Generation Request

**`POST /api/jobs`**

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Python Workshop 2024",
    "organizer_name": "Tech Academy",
    "issue_date": "2024-01-15",
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com"},
      {"name": "Bob Smith",    "email": "bob@example.com"},
      {"name": "Charlie Brown","email": "charlie@example.com"}
    ]
  }'
```

**Response** (`202 Accepted`):

```json
{
  "id": "a1b2c3d4-...",
  "status": "pending",
  "total_count": 3,
  "message": "Job created. Generating 3 certificate(s) in the background."
}
```

### 2. Check Job Status

**`GET /api/jobs/{job_id}`**

```bash
curl http://localhost:8000/api/jobs/a1b2c3d4-...
```

Returns full job details including a per-certificate breakdown:

```json
{
  "id": "a1b2c3d4-...",
  "event_name": "Python Workshop 2024",
  "organizer_name": "Tech Academy",
  "issue_date": "2024-01-15",
  "status": "completed",
  "total_count": 3,
  "success_count": 3,
  "failure_count": 0,
  "created_at": "...",
  "updated_at": "...",
  "certificates": [
    {
      "id": "cert-id-1",
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "status": "success",
      "error_message": null,
      "created_at": "..."
    }
  ]
}
```

### 3. List All Jobs

**`GET /api/jobs`**

```bash
curl http://localhost:8000/api/jobs
```

### 4. Download a Certificate

**`GET /api/certificates/{certificate_id}/download`**

```bash
curl -O http://localhost:8000/api/certificates/cert-id-1/download
```

Returns the PDF file. Only certificates with `status: "success"` can be downloaded.

### 5. Download All Certificates of a Job (ZIP)

**`GET /api/jobs/{job_id}/download`**

```bash
curl -o certificates.zip http://localhost:8000/api/jobs/a1b2c3d4-.../download
```

Returns a ZIP of every successfully generated PDF in the job (files named `<Recipient_Name>_<certificate_id>.pdf`). Returns `400` if none are ready yet. Can be called while a job is still processing to get what's done so far.

---

## Design Decisions

### Framework — FastAPI

- Async-native with excellent performance.
- Pydantic integration provides automatic request validation and OpenAPI docs.
- Modern Python (type hints, `asynccontextmanager` lifespan).

### Database — SQLite via SQLAlchemy

- **Relational** as required, supporting the Job → Certificate foreign-key relationship.
- **Zero configuration** — no database server to install or manage.
- **Swappable** — changing to PostgreSQL requires only updating `DATABASE_URL` and installing `psycopg2`; no code changes needed.

### Background Processing — Thread Pool Executor

The API returns `202 Accepted` immediately and generates certificates in a background thread.

**Why not synchronous?**
A request with hundreds of recipients would block the HTTP response for seconds or minutes. Returning immediately and processing in the background is the standard pattern for long-running work.

**Why not Celery?**
Celery requires a message broker (Redis or RabbitMQ), adding operational complexity. Python's built-in `concurrent.futures.ThreadPoolExecutor` with `asyncio.run_in_executor()` provides genuine background processing with zero external dependencies.

**Trade-off:** If the server process crashes mid-generation, in-flight work is lost. For a production system at scale, Celery + Redis would be the natural upgrade path.

### Certificate Generation — ReportLab

- Mature, pure-Python PDF library — no system-level dependencies (unlike `wkhtmltopdf` or `weasyprint`).
- Produces a professional landscape A4 certificate with decorative borders, gold accents, recipient information, and a unique certificate ID.

### Validation: Request-Level vs. Recipient-Level

- **Request-level** fields (`event_name`, `organizer_name`, `issue_date`, a non-empty `recipients` list of at most 10,000) are validated strictly — any problem returns `422` and no job is created.
- **Recipient-level** data is validated **per recipient**. One bad email in a list of 500 should not reject the other 499. Invalid recipients are stored as certificates with `status: "failed"` and an `error_message` such as `Invalid recipient: email: Value error, Invalid email format`; valid recipients are generated normally. `total_count` includes all submitted recipients, and invalid ones count toward `failure_count`.

### Progress Tracking

`success_count` / `failure_count` are committed after **every** certificate, so polling `GET /api/jobs/{job_id}` while a job is `processing` shows live progress (`(success_count + failure_count) / total_count`).

### Failure Isolation

Each certificate is generated independently inside a try/except block, and progress is committed to the database after each certificate. A failure in one certificate does not prevent the others from being generated. A job is `completed` if at least one certificate succeeded (inspect per-certificate statuses for partial failures) and `failed` only if none did. The job status endpoint provides enough information to identify which certificates succeeded and which failed (including error messages).

### Testing Strategy

Tests mock the `process_job_background` coroutine (replacing it with a no-op) so that all processing is deterministic and synchronous. Tests that need to verify generation results call `_process_certificates()` directly. This avoids flaky timing issues while still exercising the real generation code.

---

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # Environment-based settings
│   ├── database.py              # SQLAlchemy engine & session
│   ├── models.py                # Job & Certificate ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── routes.py                # API endpoints
│   ├── services.py              # Job creation + background processing
│   └── certificate_template.py  # ReportLab PDF renderer
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_create_job.py       # Job creation
│   ├── test_validation.py       # Input validation
│   ├── test_generation.py       # PDF generation
│   ├── test_status.py           # Status tracking
│   ├── test_failure.py          # Failure handling
│   └── test_retrieval.py        # Certificate download
├── certificates/                # Generated PDFs (created at runtime)
├── requirements.txt
└── README.md
```
