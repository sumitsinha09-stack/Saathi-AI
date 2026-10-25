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
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### 5. Automated Testing

Run the full test suite (12 tests covering verification, HMAC validation, deduplication, voice message handling, and Meta error handling):

```bash
pytest
```

---

### 6. Verification & Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `http://127.0.0.1:8000/` | `GET` | Service identity and status |
| `http://127.0.0.1:8000/health` | `GET` | PostgreSQL and Ollama connectivity status |
| `http://127.0.0.1:8000/webhook` | `GET` | Meta Webhook Handshake verification |
| `http://127.0.0.1:8000/webhook` | `POST` | Event receiver, HMAC-SHA256 signature check & echo loop |
| `http://127.0.0.1:8000/docs` | `GET` | Interactive Swagger API documentation |

---

### 7. Reliability & Deduplication Architecture

- **PostgreSQL Idempotency Table (`processed_messages`)**:
  Stores `message_id` as primary key. Concurrent duplicate webhook deliveries from Meta are caught and deduplicated before queuing any outbound replies.
- **Asynchronous Execution**:
  Webhooks respond with HTTP 200 within milliseconds to satisfy Meta's strict timeout (< 3 seconds), and outbound acknowledgments are dispatched via FastAPI `BackgroundTasks`.
- **Note on Background Tasks**:
  FastAPI `BackgroundTasks` run in-process. If the application server process terminates while a task is queued, that specific delivery may not complete. In future production hardening (Phase 6), Celery or Redis streams can be layered for distributed retries.
