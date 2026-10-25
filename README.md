# Saathi AI (Samaran) — Cybercrime Reporting Assistant

> **Emergency WhatsApp Voice-Complaint Assistant for Cyber-Fraud Victims in India**

Saathi AI helps victims of financial cyber-fraud (UPI impersonation, phishing, fake loan apps, KYC scams) capture, transcribe, structure, and immediately initiate reporting during the critical **"Golden Hour"** through WhatsApp voice notes.

---

## Architecture & Core Safety Principles

- **Zero Paid AI APIs**: Powered exclusively by local, self-hosted open-source models:
  - **Faster-Whisper**: Local speech-to-text with Indic language support.
  - **Ollama (`qwen3:8b` / `qwen3:4b`)**: Local structured information extraction.
- **Strict Privacy & Zero Credential Capture**:
  - Never solicit, capture, or persist **OTPs, PINs, passwords, or full card numbers**.
  - Audio files are stored in transient spool memory and **deleted immediately after transcription**.
- **Mandatory User Consent Gate**:
  - No reporting, bank emails, or mock FIR generation occurs without explicit user confirmation (`Confirm` / `Edit` / `Cancel` buttons).
- **Transparency**:
  - Every simulated feature (FIR generation, complaint timeline) is prominently watermarked with **`Demo mode`**.
- **Case Reference Prefix**:
  - All complaints follow the standard format: `SAI-YYYY-XXXX` (e.g., `SAI-2026-0001`).

---

## Directory Structure

```text
samaran/
├── backend/
│   ├── app/
│   │   ├── __init__.py       # Package definition
│   │   ├── config.py         # Pydantic configuration & env validation
│   │   ├── database.py       # Async SQLAlchemy engine & session factory
│   │   ├── models.py         # ProcessedMessage idempotency database model
│   │   ├── main.py           # FastAPI app, CORS, lifespan, /, /health, /docs
│   │   ├── routers/
│   │   │   └── webhook.py    # GET & POST /webhook handlers with HMAC verification
│   │   └── services/
│   │       └── whatsapp.py   # Meta WhatsApp Cloud API client & echo acknowledgment
│   ├── tests/
│   │   ├── conftest.py       # Pytest fixtures & isolated test database
│   │   └── test_webhook.py   # 12 automated unit & integration test cases
│   ├── venv/                 # Python 3.14 virtual environment (git-ignored)
│   ├── requirements.txt      # Backend dependencies
│   └── .env.example          # Example backend configuration
├── portal/                   # Next.js web portal (Phase 1 placeholder)
├── .env                      # Local environment variables & secrets (git-ignored)
├── .env.example              # Root configuration template
├── .gitignore                # Secrets, caches, venv & audio protection
├── docker-compose.yml        # PostgreSQL database service
├── pytest.ini                # Pytest configuration
├── PROGRESSION.md            # Comprehensive project roadmap & changelog
└── README.md                 # System documentation & setup guide
```

---

## Phase 2: WhatsApp Webhook & Echo Bot Setup

### 1. Configure Local Environment (`.env`)

Ensure your `.env` contains the required WhatsApp configuration:

```ini
# PostgreSQL
POSTGRES_DB=samaran
POSTGRES_USER=samaran_user
POSTGRES_PASSWORD=samaran_dev_pass_2026
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
DATABASE_URL=postgresql+psycopg://samaran_user:samaran_dev_pass_2026@127.0.0.1:5433/samaran

# Ollama LLM
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b

# WhatsApp Cloud API (Meta for Developers)
WHATSAPP_VERIFY_TOKEN=your_custom_verify_token
WHATSAPP_ACCESS_TOKEN=your_meta_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_APP_SECRET=your_meta_app_secret
WHATSAPP_API_VERSION=v21.0
```

---

### 2. Expose Local Backend (Tunnel Setup)

To allow Meta to deliver webhook events to your local machine (`http://127.0.0.1:8000`), choose one of the following public tunneling methods:

#### Option A: ngrok (Recommended)
1. Install ngrok via Homebrew:
   ```bash
   brew install ngrok/ngrok/ngrok
   ```
2. Authenticate (first time only):
   ```bash
   ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
   ```
3. Start the tunnel on port 8000:
   ```bash
   ngrok http 8000
   ```
4. Copy the public forwarding HTTPS URL (e.g. `https://abc12345.ngrok-free.app`).
   Your webhook callback URL is:
   ```text
   https://abc12345.ngrok-free.app/webhook
   ```

#### Option B: Cloudflare Tunnel (Free, no account required for quick tunnels)
1. Install cloudflared via Homebrew:
   ```bash
   brew install cloudflared
   ```
2. Start an ad-hoc tunnel:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
3. Copy the generated `*.trycloudflare.com` URL (e.g. `https://xyz.trycloudflare.com`).
   Your webhook callback URL is:
   ```text
   https://xyz.trycloudflare.com/webhook
   ```

---

### 3. Meta Developer Dashboard Setup

Follow these exact steps to connect your WhatsApp sandbox to your local server:

1. **Access Meta Developer Dashboard**:
   - Go to [developers.facebook.com](https://developers.facebook.com/) and open your **Saathi-AI** app.
2. **Retrieve App Secret**:
   - Go to **App Settings** -> **Basic**.
   - Under **App Secret**, click **Show** and copy the value into your `.env` as `WHATSAPP_APP_SECRET`.
3. **Retrieve Phone Number ID & Access Token**:
   - In the left sidebar, click **WhatsApp** -> **API Setup**.
   - Copy the **Phone number ID** into `WHATSAPP_PHONE_NUMBER_ID`.
   - Copy the temporary **Access token** into `WHATSAPP_ACCESS_TOKEN`.
   - Under **To**, select **Manage phone number list** and add your personal WhatsApp number with `+91` country code. Verify via OTP.
4. **Configure Webhook**:
   - In the left sidebar, click **WhatsApp** -> **Configuration**.
   - Under **Webhook**, click **Edit**.
   - **Callback URL**: Enter `https://YOUR_PUBLIC_TUNNEL/webhook` (e.g., `https://abc.ngrok-free.app/webhook`).
   - **Verify Token**: Enter the exact string configured in your `.env` (`WHATSAPP_VERIFY_TOKEN`).
   - Click **Verify and Save**. Meta will execute a `GET /webhook` request. If tokens match, verification succeeds immediately.
5. **Subscribe to Webhook Fields**:
   - In the Webhook configuration table, locate **messages**.
   - Click **Subscribe**. This instructs Meta to forward incoming text and voice notes to your `/webhook`.

---

### 4. Running the Application

```bash
# 1. Start Docker Database
docker compose up -d

# 2. Activate Virtual Environment
source backend/venv/bin/activate

# 3. Start FastAPI Application
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Phase 3: Local Voice Transcription (Faster-Whisper)

### 1. Whisper Model Configuration & Hardware Guidelines

Voice notes are transcribed locally using **Faster-Whisper** with zero audio sent to third-party APIs.
The Whisper model is configurable via environment variables in `.env`:

```ini
# Faster-Whisper Speech Recognition Configuration
WHISPER_MODEL_SIZE=medium       # Default: medium. Supports: tiny, base, small, medium, large-v3
WHISPER_DEVICE=cpu              # 'cpu' or 'cuda' (if NVIDIA GPU available)
WHISPER_COMPUTE_TYPE=int8       # 'int8' for CPU, 'float16' for CUDA
WHISPER_BEAM_SIZE=5             # Beam search size
WHISPER_VAD_FILTER=true         # Voice Activity Detection
```

#### Hardware & Resource Comparison

| Model | Disk Footprint | RAM Required | Inference Speed (CPU) | Indic Accuracy (Hindi/Tamil) | Recommended For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`medium`** (Default) | ~1.5 GB | ~2.5 GB | 2–5 seconds | High (92–98% accuracy) | Local laptops, Apple Silicon, standard servers |
| **`large-v3`** | ~3.1 GB | ~5.5 GB | 6–12 seconds | Highest (97–99% accuracy) | Production servers, GPUs, noisy voice notes |
| **`base`** | ~140 MB | ~1.0 GB | < 1 second | Moderate (Lower on Tamil) | Resource-constrained lightweight testing |

To switch models, simply change `WHISPER_MODEL_SIZE=large-v3` in `.env` and restart the server. No code modifications are needed.

---

### 2. Testing on Desktop & Mobile Phones

1. **Access from Desktop**:
   - Open [http://localhost:8000/](http://localhost:8000/) in your browser.
   - Navigate to the **Incident Voice Studio**.
   - Click the microphone icon to record a voice note, or drag-and-drop an audio file (`.wav`, `.mp3`, `.ogg`, `.webm`, `.m4a`).
   - Click **Send Incident Audio**.
   - Watch the stepper transition: **Uploading ➔ Received ➔ Transcribing ➔ Completed**.
   - The detected language badge (e.g. `🇮🇳 Hindi (99% conf)`) and transcript in native script will appear with a **Copy Transcript** button.

2. **Access from a Mobile Phone on Local Wi-Fi**:
   - Find your computer's local Wi-Fi IP address (e.g., `192.168.1.5`):
     ```bash
     ipconfig getifaddr en0
     ```
   - Connect your smartphone to the same Wi-Fi network.
   - For microphone access on mobile browsers without HTTPS:
     - Use a local tunnel (`cloudflared tunnel --url http://127.0.0.1:8000` or `ngrok http 8000`), or
     - Use the **Upload Audio** tab on mobile to select voice notes recorded with the native voice recorder app.
   - The mobile-optimized UI provides full responsive playback, progress bars, and transcript display.

---

### 3. Automated Testing

Run the full automated test suite (covering audio validation, status transitions, Faster-Whisper multi-dialect transcription, zero-retention file purging, and local translation):

```bash
# Run voice upload & validation tests
pytest backend/tests/test_voice.py

# Run Faster-Whisper local transcription tests (Hindi, Tamil, English)
pytest backend/tests/test_transcription.py

# Run local translation tests (Argos Translate & Ollama qwen2.5:1.5b)
pytest backend/tests/test_translation.py

# Run full test suite
pytest
```

---

### 4. Verification & Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `http://127.0.0.1:8000/` | `GET` | Landing page & Voice Studio (HTML) or API metadata (JSON) |
| `http://127.0.0.1:8000/api/voice` | `POST` | Upload voice note (multipart/form-data, ≤5MB, ≤2min) |
| `http://127.0.0.1:8000/api/voice/status/{token}` | `GET` | Poll upload, transcription & translation status |
| `http://127.0.0.1:8000/api/voice/translate` | `POST` | Translate transcript to natural English locally (`{"token": str}`) |
| `http://127.0.0.1:8000/health` | `GET` | PostgreSQL and Ollama connectivity status |
| `http://127.0.0.1:8000/webhook` | `GET` | Meta Webhook Handshake verification |
| `http://127.0.0.1:8000/webhook` | `POST` | Event receiver, HMAC-SHA256 signature check & echo loop |
| `http://127.0.0.1:8000/docs` | `GET` | Interactive Swagger API documentation |

---

### 5. Reliability & Deduplication Architecture

- **PostgreSQL Idempotency Table (`processed_messages`)**:
  Stores `message_id` as primary key. Concurrent duplicate webhook deliveries from Meta are caught and deduplicated before queuing any outbound replies.
- **Asynchronous Background Processing**:
  Both WhatsApp replies and Faster-Whisper audio transcriptions are dispatched via FastAPI `BackgroundTasks`. The upload endpoints return immediately without blocking user requests.
- **Strict Zero-Retention Privacy Policy**:
  Audio files are immediately unlinked from disk in a `finally` block post-transcription, ensuring zero permanent audio data retention on the server.
