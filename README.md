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
│   │   ├── __init__.py
│   │   └── main.py          # FastAPI application & health monitoring
│   ├── venv/                # Isolated Python virtual environment
│   ├── requirements.txt     # Backend dependencies
│   └── .env.example         # Example backend configuration
├── portal/                  # Next.js web portal (Phase 1 placeholder)
├── .env                     # Local environment variables & secrets (git-ignored)
├── .env.example             # Root configuration template
├── .gitignore               # Secrets, caches, venv & audio protection
├── docker-compose.yml       # PostgreSQL database service
└── README.md                # System documentation & setup guide
```

---

## Phase 1: Environment & Setup Guide

### 1. Prerequisites

Ensure the following tools are installed on your macOS system:

- **Python 3.10+**: Available via Homebrew (`brew install python@3.12` or Python 3.14/3.15).
- **Docker & Docker Compose**: Installed via Docker Desktop (`/Applications/Docker.app`).
- **Ollama**: Installed via Homebrew (`brew install ollama`).
- **Node.js (v18+) & npm**: For future Next.js portal development.
- **Git**: For source version control.

### 2. Environment Configuration

Copy the example environment file to create your active `.env`:

```bash
cp .env.example .env
```

Review `.env` to verify your PostgreSQL and Ollama configuration:

```ini
# PostgreSQL
POSTGRES_DB=samaran
POSTGRES_USER=samaran_user
POSTGRES_PASSWORD=samaran_dev_pass_2026
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://samaran_user:samaran_dev_pass_2026@127.0.0.1:5432/samaran

# Ollama LLM
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

### 3. Launch PostgreSQL Database

Start the PostgreSQL 16 container with healthchecks:

```bash
docker compose up -d
```

Verify that the database is healthy:

```bash
docker ps -f "name=samaran-postgres"
```

### 4. Start Ollama and Download AI Model

Start Ollama as a local background service:

```bash
brew services start ollama
```

Download the Qwen model:

```bash
# For standard systems:
ollama pull qwen3:8b

# For machines with 8 GB RAM (recommended to prevent memory pressure):
ollama pull qwen3:4b
```

Verify that Ollama responds:

```bash
ollama run qwen3:8b "Respond with: Saathi AI LLM engine is ready."
```

### 5. Backend Setup & Virtual Environment

Create and activate the Python virtual environment:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..
```

### 6. Run the FastAPI Application

From the project root:

```bash
source backend/venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Verification & Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `http://127.0.0.1:8000/` | `GET` | Service identity and status |
| `http://127.0.0.1:8000/health` | `GET` | Live PostgreSQL and Ollama connectivity status |
| `http://127.0.0.1:8000/docs` | `GET` | Interactive Swagger API documentation |
| `http://127.0.0.1:8000/redoc` | `GET` | ReDoc API specifications |

Sample `/health` response:
```json
{
  "status": "healthy",
  "timestamp": "2026-10-25T10:45:00.000000Z",
  "configured_model": "qwen3:8b",
  "services": {
    "backend": "healthy",
    "database": "connected",
    "ollama": "available"
  }
}
```

---

## WhatsApp Cloud API Configuration Guide (Meta for Developers)

To integrate WhatsApp messaging in subsequent phases:

### Step 1: Create a Meta Developer Account
1. Visit [developers.facebook.com](https://developers.facebook.com/) and log in with your Facebook account.
2. Complete developer registration if accessing for the first time.

### Step 2: Create a Meta App
1. Navigate to **My Apps** -> **Create App**.
2. Select **Other** as the use case -> click **Next**.
3. Select **Business** as the App Type -> click **Next**.
4. Enter an App name (e.g. `Saathi-AI-Dev`), provide your email, and select your Business Portfolio (or leave default).

### Step 3: Add the WhatsApp Product
1. On the App Dashboard, locate **WhatsApp** in the list of products.
2. Click **Set up**. This automatically creates a sandbox WhatsApp Business Account (WABA).

### Step 4: Configure Test Phone Number & Authorized Recipients
1. In the sidebar under **WhatsApp**, select **API Setup**.
2. Meta provides a free **Test phone number** with pre-configured templates.
3. In the **Send and receive messages** panel, find the **To** phone number dropdown.
4. Select **Manage phone number list** and add your personal WhatsApp number (with India country code `+91`).
5. Enter the verification code received on your phone via SMS/WhatsApp.

### Step 5: Extract Credentials for `.env`
Collect the following configuration values from Meta:
- **`WHATSAPP_PHONE_NUMBER_ID`**: Displayed under *Phone number ID* on the API Setup page.
- **`WHATSAPP_BUSINESS_ACCOUNT_ID`**: Displayed under *WhatsApp Business Account ID*.
- **`WHATSAPP_ACCESS_TOKEN`**: Copy the 24-hour temporary access token for development, or generate a permanent token via *Meta Business Settings -> System Users*.
- **`WHATSAPP_VERIFY_TOKEN`**: A custom secret token you define (e.g., `saathi_webhook_token_2026`) used to verify webhook handshakes in Phase 2.

Add these values to your local `.env` file. Never commit `.env` to Git.

---

## Troubleshooting

- **PostgreSQL port 5432 already in use**:
  If a local PostgreSQL instance is running on port 5432, change `POSTGRES_PORT=5433` in `.env` and `docker-compose.yml`.
- **Ollama unreachable**:
  Check if the Ollama daemon is running with `curl http://127.0.0.1:11434/`. If stopped, run `brew services restart ollama`.
- **Docker daemon connection error**:
  Ensure Docker Desktop is open (`open -a Docker`).
