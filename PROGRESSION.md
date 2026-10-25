# Saathi AI — Project Progression & Roadmap Tracker

> **Tracking Document**: Records all completed milestones, current progress, architectural decisions, and upcoming phase deliverables. Updated continuously after every major implementation step.

---

## 📊 High-Level Status Overview

| Phase | Description | Status | Completion Date |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Environment and Project Initialization** | ✅ **Completed** | 2026-10-25 |
| **Phase 2** | **WhatsApp Webhook and Echo Bot** | ✅ **Completed** | 2026-10-25 |
| **Phase 2.5** | **Voice Note Recording, Validation & Upload System** | ✅ **Completed** | 2026-10-26 |
| **Phase 3** | **Local Voice Transcription (Faster-Whisper, Zero Retention)** | ✅ **Completed** | 2026-10-26 |
| **Phase 3.5** | **Automatic Transcription & Optional English Translation** | ✅ **Completed** | 2026-10-26 |
| **Phase 4** | **Ollama (Qwen3) Structured Extraction & Credential Redaction** | ⏳ *Pending* | Upcoming |
| **Phase 5** | **WhatsApp Interactive Review Gate (Confirm / Edit / Cancel)** | ⏳ *Pending* | Upcoming |
| **Phase 6** | **Automated Relief Actions (Bank Dispute Email, PDF, 1930, FIR)** | ⏳ *Pending* | Upcoming |
| **Phase 7** | **Next.js Portal & Live Status Timeline** | ⏳ *Pending* | Upcoming |

---

## 📝 Phase-by-Phase Detailed Changelog

### Phase 3.5: Automatic Transcription & Optional English Translation (Completed: 2026-10-26)

#### 1. Automatic Transcription Pipeline
- **Auto-send Triggers**:
  - Automatically submits voice recordings upon stopping the recorder or selecting/dropping an audio file without requiring manual confirmation.
  - Retains manual "Transcribe Voice Note" and "Transcribe Audio File" buttons for full user control and retry workflows.
- **Strict Native Dialect Preservation**:
  - Automatically identifies spoken languages including Hindi, Tamil, and English.
  - Hindi speech is preserved in Hindi script (Devanagari).
  - Tamil speech is preserved in Tamil script.
  - English speech is preserved in English.
  - Spoken Hindi and Tamil are never auto-translated into English during initial transcription.

#### 2. Local Translation Engine & Endpoints
- **High-Accuracy Local Translation Strategy (`backend/app/services/translation_service.py`)**:
  - 100% offline local inference: zero audio or text sent to external translation APIs.
  - **Ollama (`qwen2.5:3b`) [Primary Engine]**: High-accuracy Indic-to-English translation specifically engineered for Indian cybercrime narratives. Correctly handles conversational Hindi, Devanagari loanwords ("फ्रॉड कॉल" $\rightarrow$ *fraud call*, "बैंक अकांट" $\rightarrow$ *bank account*, "पैसे कट गए" $\rightarrow$ *money debited*), Tamil, and Hinglish. Preserves victim perspective, names, dispute context, and financial amounts (e.g., ₹10,000, ₹25,000).
  - **Argos Translate (CTranslate2) [Emergency Fallback]**: Pre-packaged offline statistical fallback for basic phrases if Ollama daemon is unreachable.
  - **English Passthrough**: Detects English speech and marks translation as unnecessary while keeping text verbatim.
- **Secure Translation API (`POST /api/voice/translate`)**:
  - Accepts secure tracking token and optional `force_refresh` flag.
  - Validates cryptographic token and ensures transcription has completed before allowing translation.
  - Caches generated translations on `VoiceUpload.english_translation` to return cached results on subsequent requests without redundant computation.
  - Supports `force_refresh: true` to bypass stale or low-quality cached translations.
  - Updates DB without overwriting or modifying original transcript.
  - Internal server paths, API secrets, and stack traces strictly sanitized from responses.

#### 3. Responsive User Interface Order (1 through 8)
- Arranged cleanly according to strict specifications:
  1. Record or upload audio (Live recording tab with waveform or File dropzone).
  2. Audio playback preview player with duration badge.
  3. Send & Transcribe action button.
  4. Transcription progress indicator with 4-step timeline (`Uploading ➔ Received ➔ Transcribing ➔ Completed`).
  5. **Original Transcript** section with detected language pill and flag.
  6. **Translate to English** button with animated spinner and "already in English" notification.
  7. **English Translation** section (visible only when translation is requested, displayed simultaneously below original transcript).
  8. Copy buttons: dedicated **Copy Transcript** and **Copy Translation** buttons with clipboard feedback.
  - Includes a **Hide Translation / Show Translation** toggle button.

---

### Phase 3: Local Voice Transcription & Faster-Whisper Pipeline (Completed: 2026-10-26)

#### 1. Faster-Whisper Local Integration & Model Architecture
- **Inference Engine (`backend/app/services/transcription_service.py`)**:
  - Embedded `faster-whisper` (v1.2.1) running completely offline on the backend without sending audio to external APIs.
  - Initialized as a cached thread-safe singleton (`TranscriptionService.get_model()`), loading the weights once and reusing across all requests.
  - Model configured via environment variables (`WHISPER_MODEL_SIZE=medium`, device `cpu`, compute type `int8`, beam size `5`).
  - Seamlessly upgradable to `large-v3` by changing `WHISPER_MODEL_SIZE=large-v3` in `.env` without modifying code.
  - Integrated resilient fallback: if an invalid model name or corrupted weights are configured, automatically falls back to `tiny`.
  - PyAV 19+ compatibility fix: resolved `metadata_errors` incompatibility by monkeypatching `av.open` to safely filter out deprecated kwargs.
  - Multi-dialect VAD handling: automatically disables aggressive Silero VAD filtering if silence is falsely detected on short audio notes, preventing dropped transcripts.

#### 2. Strict Spoken Language Preservation & Detection
- **Non-Translation Guarantee (`task="transcribe"`)**:
  - The model transcribes audio in the original spoken language and script. Spoken Hindi and Tamil are never translated into English.
  - Returns detected ISO-639-1 code (`hi`, `ta`, `en`, `bn`, `te`, etc.), human-readable language name, and confidence score (`0.0 - 1.0`).
  - Native script preserved: Hindi is transcribed in Hindustani/Devanagari, Tamil in Tamil script (`\u0B80 - \u0BFF`), and English in English.

#### 3. Asynchronous Background Processing & Zero Retention
- **Non-blocking Upload Pipeline (`POST /api/voice`)**:
  - Endpoint validates audio format, MIME type, size (≤5MB), and duration (≤2 min), saves to temporary spool, and returns upload token immediately (`status: "received"`).
  - Transcription runs asynchronously via FastAPI `BackgroundTasks` without blocking HTTP requests.
- **Strict Zero-Retention Privacy Guarantee**:
  - Temporary audio files (`backend/storage/voice_notes/{token}.{ext}`) are deleted immediately inside a `finally` block upon completion of transcription, regardless of whether inference succeeded or failed.
  - No customer audio is permanently stored on the server.
  - System paths and internal tracebacks are strictly excluded from API responses.
- **Status Endpoint (`GET /api/voice/status/{token}`)**:
  - Returns current job lifecycle: `received` ➔ `transcribing` ➔ `completed` or `failed`.
  - On `completed`: returns `transcript`, `language`, `language_name`, and `language_probability`.

#### 4. Frontend Studio Integration
- **Transcription UI & Stepper (`saathi-ai-landing/index.html`, `styles.css`, `script.js`)**:
  - Added dedicated stepper state: **Uploading ➔ Received ➔ Transcribing ➔ Completed**.
  - Polls status every 1.5s until completion or timeout.
  - On completion: renders sleek **Transcript Card** with national flag badge (🇮🇳 Hindi, 🇮🇳 Tamil, 🇬🇧 English), detected confidence score, and native transcript text box.
  - One-click **Copy Transcript** button with animated clipboard feedback.
  - Friendly error handling with **Retry Job** button allowing instant re-submission without re-recording.

#### 5. Synthetic Scam Voice-Note Dataset & Evaluation
- Generated 5 native synthetic scam voice-note audio samples in `backend/tests/test_data/synthetic_scams/`:
  1. `sample1_bank_otp_hindi.wav`: Fake bank manager requesting OTP (Hindi, Voice: Lekha).
  2. `sample2_kyc_suspension_hindi.wav`: Fraudulent KYC deactivation threat (Hindi, Voice: Lekha).
  3. `sample3_lottery_prize_tamil.wav`: Lottery prize registration fee scam (Tamil, Voice: Vani).
  4. `sample4_account_freeze_tamil.wav`: Fake account freeze threat (Tamil, Voice: Vani).
  5. `sample5_customer_support_pin_english.wav`: Fraudulent debit card support asking for ATM PIN (English, Voice: Rishi).
- Created `manifest.json` detailing scenario, speaker, script, language, and keywords for each sample.
- Built automated test suite `backend/tests/test_transcription.py` verifying all 5 samples, language detection, non-translation, zero-retention deletion, and end-to-end API polling.
- All 24 tests passed (16 in `test_voice.py`, 8 in `test_transcription.py`).

### Phase 2.5: Voice Note Recording, Validation & Upload System (Completed: 2026-10-26)

#### 1. Frontend Implementation
- **Voice Note Studio Interface (`saathi-ai-landing/index.html`)**:
  - Embedded modern, mobile-friendly Studio with a large circular **Record** button, pulsing ripple animations, and digital timer (`00:00 / 02:00`).
  - Web Audio API dynamic 20-bar frequency visualizer animating live during voice recording.
  - Recording controls: **Start, Pause, Resume, Stop, and Discard/Delete**.
  - Integrated preview player for playback before sending.
  - **Audio File Upload Tab**: Drag-and-drop zone with support for `.webm`, `.ogg`, `.mp3`, `.wav`, and `.m4a` files (up to 5 MB and 2 minutes duration).
  - Real-time `XMLHttpRequest` upload progress bar (`0% - 100%`) with dedicated stepper: Uploading ➔ Received ➔ Processing ➔ Completed.
  - Status polling client with 1.5s interval and copyable cryptographic token card.

#### 2. Backend & Security Architecture
- **Voice Ingestion Endpoint (`POST /api/voice`)**:
  - Multi-part form-data receiver with zero credential retention policy.
  - Multi-tier validation: rejects empty files (HTTP 400), oversized files > 5MB (HTTP 413), and recordings > 2 minutes / 120s (HTTP 400).
  - Magic byte inspection validates actual binary headers (EBML/WebM, RIFF/WAV, OggS, ID3/MPEG, ftyp/M4A), rejecting forged files (HTTP 415).
  - Audio duration validated using `tinytag`, `mutagen`, and `ebmlite`.
  - Cryptographically secure token (`secrets.token_urlsafe(32)`) assigned to each upload.
  - Safe storage: files saved with sanitized `{token}.{format}` under `backend/storage/voice_notes`. Internal paths and server details are strictly isolated and never leaked in API responses.
- **Status Endpoint (`GET /api/voice/status/{token}`)**:
  - Polling endpoint returning upload status (`received`, `processing`, `completed`, `failed`), sanitized metadata, and format.
- **Database & Storage Models**:
  - Added `VoiceUpload` SQLAlchemy model in [`backend/app/models.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/app/models.py) with 24-hour expiration policy.
  - Added resilient memory fallback cache for offline development.
- **Automated Testing Suite**:
  - Created 16 comprehensive automated tests in [`backend/tests/test_voice.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/tests/test_voice.py) covering WAV, MP3, OGG, WebM, oversized payloads, excessive durations, empty files, lifecycle updates, and browser HTML serving.
  - Full project test suite passed with 100% success rate (33/33 tests).

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
- **Ollama AI Integration & Dynamic Response Pipeline**:
  - Implemented `AIService` in [`backend/app/services/ai.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/app/services/ai.py) replacing static echo with real-time Ollama assistance.
  - Guided prompt instructions for Indian cyber-fraud victims (1930 Helpline, bank account blocking, cybercrime.gov.in).
  - Robust fallback: automatically provides emergency guidance if Ollama is unreachable or times out.
  - Added `mark_message_as_read` to send WhatsApp read receipts via Meta Cloud API.
- **Automated Meta Graph API Diagnostics**:
  - Implemented [`backend/scripts/verify_meta_setup.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/scripts/verify_meta_setup.py) for programmatic token inspection, phone number verification, WABA auto-discovery, and automatic WABA app subscription.
- **Automated Testing & Quality Assurance**:
  - Built comprehensive test suites with 17 tests across [`test_webhook.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/tests/test_webhook.py) and [`test_ai_service.py`](file:///Users/sumitsinha/Documents/Saathi%20AI/backend/tests/test_ai_service.py).
  - 100% pass rate (`17 passed in 0.44s`).
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
