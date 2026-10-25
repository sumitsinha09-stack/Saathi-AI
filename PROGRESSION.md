# Saathi AI — Project Progression & Roadmap Tracker

> **Tracking Document**: Records all completed milestones, current progress, architectural decisions, and upcoming phase deliverables. Updated continuously after every major implementation step.

---

## 📊 High-Level Status Overview

| Phase | Description | Status | Completion Date |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Environment and Project Initialization** | ✅ **Completed** | 2026-10-25 |
| **Phase 2** | **WhatsApp Cloud API Webhook & Ingestion Pipeline** | ⏳ *Pending* | Upcoming |
| **Phase 3** | **Audio Ingestion & Faster-Whisper Pipeline (Zero Retention)** | ⏳ *Pending* | Upcoming |
| **Phase 4** | **Ollama (Qwen3) Structured Extraction & Credential Redaction** | ⏳ *Pending* | Upcoming |
| **Phase 5** | **WhatsApp Interactive Review Gate (Confirm / Edit / Cancel)** | ⏳ *Pending* | Upcoming |
| **Phase 6** | **Automated Relief Actions (Bank Dispute Email, PDF, 1930, FIR)** | ⏳ *Pending* | Upcoming |
| **Phase 7** | **Next.js Portal & Live Status Timeline** | ⏳ *Pending* | Upcoming |

---

## 📝 Phase-by-Phase Detailed Changelog

### Phase 1: Environment & Project Initialization (Completed: 2026-10-25)

#### 1. Environment & Tools Verification
- **Python**: Installed Python 3.14.7 (`/opt/homebrew/opt/python@3.14/bin/python3.14`).
- **Git**: Initialized Git repository; verified Git version 2.50.1.
- **Docker & Docker Compose**: Configured and verified with Docker 29.8.0 and Docker Compose v5.5.1.
- **Node.js & npm**: Verified Node `v24.15.0` and npm `11.12.1`.
- **Ollama**: Installed Ollama `0.40.11` via Homebrew and registered as background service (`brew services start ollama`).

#### 2. AI Model & Hardware Architecture
- Analyzed Apple Silicon hardware profile: Apple M1 with 8.0 GB unified RAM.
- **`qwen3:8b` (5.2 GB)**: Downloaded and verified with Metal GPU acceleration for deep reasoning.
- **`qwen3:4b` (2.5 GB)**: Downloaded as recommended alternative to maintain optimal system responsiveness under multi-container loads.
- Ollama verified and accessible via HTTP API at `http://127.0.0.1:11434/api/tags`.

#### 3. Containerized PostgreSQL Database
- Created [`docker-compose.yml`](file:///Users/sumitsinha/Documents/Saathi%20AI/docker-compose.yml) running PostgreSQL 16 Alpine (`samaran-postgres`).
- Configured persistent Docker volume `saathiai_postgres_data` for durable storage.
- Healthcheck configured with `pg_isready` interval 5s.
- **Port Conflict Mitigation**: Mapped container to host port `5433` (`5433:5432`) to coexist peacefully with an existing host PostgreSQL service on port `5432`.
- Verified live database connection via async Python `psycopg`.

#### 4. Backend Architecture & Virtual Environment
- Created Python virtual environment at [`backend/venv`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/venv) using Python 3.14.
- Installed dependencies in [`backend/requirements.txt`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/requirements.txt):
  - `fastapi` & `uvicorn[standard]`
  - `sqlalchemy[asyncio]` & `greenlet`
  - `psycopg[binary]`
  - `httpx`
  - `pydantic` & `pydantic-settings`
  - `faster-whisper`
  - `ollama` Python client
  - `python-dotenv`

#### 5. FastAPI Core Application
- Built [`backend/app/main.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/app/main.py) with lifespan management and CORS middleware.
- **`GET /`**: Returns service name, environment, and status.
- **`GET /health`**: Live health check querying both PostgreSQL (`SELECT 1`) and Ollama API.
- **Swagger Documentation**: Active at `http://127.0.0.1:8000/docs`.

#### 6. Security, Git, and Privacy Guardrails
- Created [`.gitignore`](file:///Users/sumitsinha/Documents/Saathi%20AI/.gitignore) to exclude `.env`, `backend/venv/`, `__pycache__/`, and transient audio extensions (`*.ogg`, `*.wav`, `*.mp3`, `*.m4a`).
- Verified zero credentials or tokens committed to Git.
- Configured [`.env.example`](file:///Users/sumitsinha/Documents/Saathi%20AI/.env.example) and [`backend/.env.example`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/.env.example) with placeholder values.
- Comprehensive setup and WhatsApp Cloud API guide documented in [`README.md`](file:///Users/sumitsinha/Documents/Saathi%20AI/README.md).

---

## 🔮 Upcoming Phases & Roadmap

### Phase 2: WhatsApp Cloud API Webhook & Ingestion Pipeline
- Implement WhatsApp webhook verification endpoint (`GET /webhook` using `WHATSAPP_VERIFY_TOKEN`).
- Implement event receiver endpoint (`POST /webhook`) to capture incoming user messages.
- Parse message metadata (sender phone, timestamp, message type: text, audio/voice, interactive button reply).
- Mock/test harness for simulating inbound WhatsApp payloads locally without ngrok.

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
