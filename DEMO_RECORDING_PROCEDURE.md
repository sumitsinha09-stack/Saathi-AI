# Saathi AI — Recorded Backup Demo Video & Capture Procedure

This document provides complete instructions for creating, playing back, and reproducing the offline backup demo recording for Saathi AI.

---

## 1. Backup Demo Video Artifact

- **Location**: `demo_assets/saathi_ai_demo_backup.webm` (also available as browser subagent recording artifact).
- **Format**: High-definition WebM video with synchronized audio/actions.
- **Workflow Covered**:
  1. Citizen landing page & voice note upload (`en_01_bank_impersonation.wav`).
  2. Faster-Whisper local speech transcription & English translation.
  3. Qwen3 structured cybercrime complaint extraction with zero hallucinations and redacted OTPs.
  4. Complaint review page (`/c/{token}`) with field edits.
  5. Citizen confirmation, sealing complaint, and generating `SAI-XXXXXX`.
  6. Post-confirmation relief: Pre-filled bank email, 1930 dialler, official cybercrime guide, formal PDF download.
  7. Simulated FIR demonstration with persistent Demo Mode banner.
  8. Public status lookup on `/helpline`.

---

## 2. Quick Offline Playback

To play the offline backup video during a presentation:

```bash
# macOS default player
open demo_assets/saathi_ai_demo_backup.webm

# Or open in Google Chrome / Safari
open -a "Google Chrome" demo_assets/saathi_ai_demo_backup.webm
```

---

## 3. Manual Reproduction Procedure

If you wish to re-record the backup video from scratch:

### Step 1: Start Backend Dev Server
```bash
cd "/Users/sumitsinha/Documents/Saathi AI"
source backend/venv/bin/activate
uvicorn backend.app.main:app --port 8000
```

### Step 2: Open Screen Recording Tool
- On macOS: Press `Cmd + Shift + 5`.
- Select **Record Selected Portion** and frame the browser window (1280x800 recommended).
- Set Audio to **Built-in Microphone** if narrating live, or None if playing synthetic audio.

### Step 3: Execute Walkthrough
Follow the exact sequence in [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md):
1. Navigate to `http://localhost:8000/`.
2. Upload `backend/tests/fixtures/voice_notes/en_01_bank_impersonation.wav`.
3. Wait for transcription and view Devanagari/English transcript.
4. Review extracted fields on `/c/{token}`.
5. Click **Edit Details**, append a note, and save.
6. Click **Confirm Complaint**.
7. Test the relief actions:
   - Click **Download Complaint PDF** (verify PDF opens).
   - Click **Simulated FIR** (point out Demo Mode banner).
8. Navigate to `/helpline` and track the reference number `SAI-XXXXXX`.

### Step 4: Save & Archive
Save the recorded video as `demo_assets/saathi_ai_demo_backup.webm`.
Ensure no sensitive personal credentials, API keys, or raw bash terminal secrets are visible in the recording.
