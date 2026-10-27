# Saathi AI — Demo Readiness Checklist & Failure Recovery Manual

This manual provides strict operational procedures to verify before presenting Saathi AI, along with contingency protocols in the event of live hardware, network, or model interruptions.

---

## 1. Pre-Flight Verification Checklist

Run the pre-flight verification script before the presentation:

```bash
backend/venv/bin/python backend/scripts/demo_health_check.py
```

### Dependency Checklist

- [x] **Backend Health**: FastAPI application starts without exceptions (`uvicorn backend.app.main:app --port 8000`).
- [x] **Frontend Assets**: Landing page (`saathi-ai-landing/index.html`) and review page (`review.html`) render cleanly without script errors.
- [x] **Storage Permissions**: `backend/storage/voice_notes` is writable and has > 5 GB free disk space.
- [x] **Faster-Whisper Model**: Loaded and responsive locally on CPU/GPU (`WHISPER_MODEL_SIZE=medium`).
- [x] **Local LLM (Ollama)**: Running on `http://127.0.0.1:11434` with `qwen3:4b` or `qwen3:8b` installed.
- [x] **Translation Pipeline**: `TranslationService` operational for Hindi/Tamil to English.
- [x] **Synthetic Test Audio**: 20 fixtures available in `backend/tests/fixtures/voice_notes/`.
- [x] **PDF Engine**: ReportLab builds test PDF successfully with valid styling.
- [x] **Rate Limiting**: Configured with production thresholds to prevent accidental demo lockouts.
- [x] **Backup Demo Video**: Offline backup recording verified and ready on presentation desktop.

---

## 2. Emergency Recovery Protocols

### Issue A: Microphone Permission Denied or Not Working
- **Symptom**: Browser displays "Microphone access blocked" or silence is recorded.
- **Root Cause**: Operating system / browser privacy permission revoked.
- **Recovery Procedure**:
  1. Do not spend time diagnosing macOS Privacy settings.
  2. Immediately switch to the **"Upload Audio"** tab on the recording interface.
  3. Select any prepared synthetic audio note from `backend/tests/fixtures/voice_notes/` (e.g. `en_01_bank_impersonation.wav` or `hi_01_bank_otp.wav`).
  4. Narrate: *"For test repeatability and privacy, we are uploading a verified synthetic victim audio note."*

### Issue B: Unsupported Browser Audio Format
- **Symptom**: Browser records in an unfamiliar codec or format unsupported by the client.
- **Recovery Procedure**:
  1. The backend automatically accepts standard `.wav`, `.webm`, `.mp3`, `.ogg`, and `.m4a`.
  2. Use Google Chrome or Apple Safari on modern macOS, which natively generates WebM/Opus or WAV.

### Issue C: Ollama Connection Failure or Timeout (> 15 seconds)
- **Symptom**: AI extraction spinner continues for more than 15 seconds.
- **Built-in Resilience**:
  1. The backend automatically executes a 3-step bounded retry.
  2. If the LLM is completely unreachable, `ExtractionService` automatically triggers a **deterministic fallback summary** and populates valid Pydantic fields without crashing.
  3. The review page displays the extracted fallback summary seamlessly with a clean status message.

### Issue D: PostgreSQL Database Disconnected
- **Symptom**: Database server goes down during the demo.
- **Built-in Resilience**:
  1. Both `VoiceService` and `ComplaintService` feature an automatic **in-memory fallback cache**.
  2. All operations (upload, status polling, edits, confirmation, relief actions, PDF generation, and helpline tracking) continue working seamlessly in memory.

### Issue E: Accidental Browser Refresh or Tab Closure
- **Symptom**: Presenter accidentally closes the tab or hits Cmd+R.
- **Recovery Procedure**:
  1. The complaint access token is stored in the URL (`/c/{token}`) and mirrored in `sessionStorage`.
  2. Reopening the URL immediately re-loads the active complaint state and history.

### Issue F: Total Laptop / Presentation Machine Freeze
- **Symptom**: Browser or machine locks up.
- **Recovery Procedure**:
  1. Switch immediately to the backup display machine or mobile device.
  2. Play the offline backup video `demo_backup_recording.webm` (see `DEMO_RECORDING_PROCEDURE.md`).
  3. Announce: *"Due to a display hardware freeze, we are presenting our synchronized live-recorded backup demonstration."*
