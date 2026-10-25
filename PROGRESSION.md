# Saathi AI — Project Progression & Roadmap Tracker

> **Tracking Document**: Records all completed milestones, current progress, architectural decisions, and upcoming phase deliverables. Updated continuously after every major implementation step.

---

## 📊 High-Level Status Overview

| Phase | Description | Status | Completion Date |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Environment and Project Initialization** | ✅ **Completed** | 2026-10-25 |
| **Phase 2** | **WhatsApp Webhook and Echo Bot** | ✅ **Completed** | 2026-10-25 |
| **Phase 3** | **Audio Ingestion & Faster-Whisper Pipeline (Zero Retention)** | ⏳ *Pending* | Upcoming |
| **Phase 4** | **Ollama (Qwen3) Structured Extraction & Credential Redaction** | ⏳ *Pending* | Upcoming |
| **Phase 5** | **WhatsApp Interactive Review Gate (Confirm / Edit / Cancel)** | ⏳ *Pending* | Upcoming |
| **Phase 6** | **Automated Relief Actions (Bank Dispute Email, PDF, 1930, FIR)** | ⏳ *Pending* | Upcoming |
| **Phase 7** | **Next.js Portal & Live Status Timeline** | ⏳ *Pending* | Upcoming |

---

## 📝 Phase-by-Phase Detailed Changelog

### Phase 2: WhatsApp Webhook and Echo Bot (Completed: 2026-10-25)

#### 1. Architecture & Security Implementation
- **Environment & Meta Graph API**:
  - Configured supported Meta Graph API version **`v21.0`**.
  - Added placeholders in `.env.example`, `backend/.env.example`, and `.env` for `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, and `WHATSAPP_API_VERSION`.
- **GET Webhook Verification Handshake (`GET /webhook`)**:
  - Validates `hub.mode == "subscribe"`.
  - Performs timing-safe comparison via `hmac.compare_digest` with `WHATSAPP_VERIFY_TOKEN`.
  - Responds with `hub.challenge` as plain text on success (200 OK), or 403 Forbidden on failure.
- **POST Webhook Receiver (`POST /webhook`)**:
  - Enforces `X-Hub-Signature-256` HMAC-SHA256 signature verification using `WHATSAPP_APP_SECRET`.
  - Constant-time comparison rejects tampered or unverified requests without processing.
  - Gracefully handles malformed JSON (HTTP 400).
  - Ignores delivery/read receipts (`statuses`) without incoming messages.
  - Returns HTTP 200 promptly to Meta within milliseconds.
- **Idempotency & Database Deduplication**:
  - Created `ProcessedMessage` SQLAlchemy model in [`backend/app/models.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/app/models.py) with `message_id` as primary key.
  - Automatic table creation on application startup via `init_db()`.
  - Validates incoming `wamid` against PostgreSQL; duplicate delivery retries from Meta are acknowledged with HTTP 200 but suppressed from generating repeat replies.
- **Outbound Acknowledgment Dispatcher**:
  - Created [`backend/app/services/whatsapp.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/app/services/whatsapp.py) using HTTPX.
  - Sends contextual reply (`context.message_id`) to the sender:
    > *"Thank you for contacting Samaran. We have received your message. Our system will help you prepare your cybercrime report in the next step."*
  - Dispatches via FastAPI `BackgroundTasks` so Meta webhook handshake never blocks.
  - Updates delivery status (`acknowledged` / `failed`) in PostgreSQL.
  - Audio and voice notes acknowledged without downloading or transcribing in this phase.
- **Automated Testing & Quality Assurance**:
  - Built comprehensive test suite [`backend/tests/test_webhook.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/tests/test_webhook.py) with 12 test cases.
  - Configured `pytest.ini` with isolated SQLite in-memory test database fixture.
  - Verified 100% pass rate (`12 passed in 0.14s`).
- **Live Local Server & Tunneling**:
  - Tested live against local Uvicorn instance on port 8000 and Docker PostgreSQL on port 5433.
  - Documented setup instructions for `ngrok` and `cloudflared` tunneling.

---

### Phase 1: Environment & Project Initialization (Completed: 2026-10-25)

#### 1. Environment & Tools Verification
- Python 3.14.7, Git 2.50.1, Docker 29.8.0, Docker Compose v5.5.1, Node.js v24.15.0, npm 11.12.1.
- Installed Ollama `0.40.11` via Homebrew as a background service.
#### 2. AI Model & Hardware Architecture
- Analyzed Apple Silicon hardware profile: Apple M1 with 8.0 GB unified RAM.
- `qwen3:8b` (5.2 GB) & `qwen3:4b` (2.5 GB) both downloaded and verified in Ollama with Metal GPU acceleration.
#### 3. Containerized PostgreSQL Database
- PostgreSQL 16 Alpine running in Docker on port 5433 with healthcheck and persistent volume `saathiai_postgres_data`.
#### 4. Backend Architecture & Virtual Environment
- Created `backend/venv` with Python 3.14.
- Installed `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `greenlet`, `psycopg[binary]`, `httpx`, `pydantic`, `faster-whisper`, `ollama`.
#### 5. FastAPI Core Application
- Built `main.py` with `/`, `/health`, and Swagger UI at `/docs`.
#### 6. Security & Documentation
- Clean `.gitignore` safeguarding secrets, caches, and media files.

---

## 🔮 Upcoming Phases & Roadmap

### Phase 3: Audio Ingestion & Faster-Whisper Pipeline
- Securely fetch audio files from Meta Media API (`graph.facebook.com/v21.0/{media-id}`).
- Spool audio to temporary memory/disk buffer.
- Transcribe audio locally using `faster-whisper` (`base` / `small` model with Hindi/Indic support).
- **Mandatory Privacy Enforcement**: Ensure immediate deletion/unlinking of audio spool file in `finally` block post-transcription.

### Phase 4: Ollama (Qwen3) Structured Extraction & Security Redaction
- System prompt engineering for Qwen3 to extract structured complaint JSON:
  - Incident date/time, victim name, loss amount, fraud category (UPI, KYC, Loan App, Investment, etc.), suspect phone/UPI/links, victim bank/account.
- **Zero Credential Rule**: Automated regex and prompt filters to strip any spoken OTPs, ATM PINs, CVVs, or full credit/debit card numbers.
- Pydantic schema validation for extracted complaint data.

### Phase 5: Interactive WhatsApp Review & Consent Gate
- Format structured complaint summary for WhatsApp display.
- Send interactive WhatsApp message with 3 action buttons:
  - `[✅ Confirm]`
  - `[✏️ Edit]`
  - `[❌ Cancel]`
- State machine in PostgreSQL: zero reporting actions triggered until `Confirm` is received.

### Phase 6: Automated Post-Confirmation Relief Actions
- **Bank Dispute Email Generator**: Draft formal grievance notice with RBI zero-liability circular reference.
- **Formal Complaint PDF**: Generate printable cybercrime incident report formatted for police and National Cyber Crime Portal standards.
- **1930 Helpline Guidance**: Instant click-to-call link and instructions for the CFCFRMS financial fraud helpline.
- **Simulated FIR & Timeline**: Watermarked explicitly with **`Demo mode`** and assigned identifier `SAI-YYYY-XXXX`.

### Phase 7: Next.js Portal
- Modern, accessible portal for victims/investigators to track complaint timeline, view generated documents, and review dispute statuses.
