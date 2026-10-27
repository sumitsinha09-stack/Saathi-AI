# Saathi AI — Live Demo Presentation Script (5–7 Minutes)

A complete, end-to-end walkthrough demonstrating Saathi AI's voice-first cybercrime complaint assistance platform.

---

## Overview & Demo Timeline

| Step | Section | Time | Goal |
|---|---|---|---|
| **1** | Introduction & Citizen Problem | 0:00 – 0:45 | Explain trauma of cyber fraud & barrier of formal legal portals. |
| **2** | Voice Note Ingestion & Validation | 0:45 – 1:30 | Upload or speak scam incident; highlight client validation & multi-language support. |
| **3** | Local Transcription & Language Detection | 1:30 – 2:30 | Show native Devanagari/Tamil transcript & optional local English translation. |
| **4** | Structured Complaint Generation | 2:30 – 3:30 | Show Qwen3 extracting factual fields with zero hallucinations and redacted OTPs. |
| **5** | Victim Review & Explicit Confirmation | 3:30 – 4:15 | Edit a field; confirm complaint to lock audit state and generate `SAI-XXXXXX`. |
| **6** | Post-Confirmation Reporting Assistance | 4:15 – 5:15 | One-tap relief: Bank freeze email, 1930 dialler, official cybercrime guide, formal PDF download. |
| **7** | Simulated FIR (Demo Mode) | 5:15 – 5:45 | Demonstrate simulated police FIR report with persistent Demo Mode banner. |
| **8** | Public Status Helpline Lookup | 5:45 – 6:15 | Track reference `SAI-XXXXXX` on `/helpline` with privacy safeguards. |
| **9** | Security, Privacy & Wrap-up | 6:15 – 7:00 | Local AI privacy, zero audio retention, rate limiting, and future roadmap. |

---

## Step-by-Step Walkthrough

### Step 1: Introduction (0:00 – 0:45)
- **What to Display**: Open home page at `http://localhost:8000/`.
- **Speaking Script**:
  > *"Every single minute in India, elderly citizens and ordinary people lose life savings to deceptive cyber frauds—fake bank KYC alerts, electricity disconnection threats, and digital arrest scams. When victims try to report the incident, formal government forms demand complex legal categorization and English descriptions, leading to despair and dropped complaints.*
  >
  > *Saathi AI bridges this gap. It is a voice-first cybercrime complaint assistant that lets citizens narrate what happened in their mother tongue—Hindi, Tamil, or English—and immediately converts spoken words into a structured complaint, formal legal PDF, and actionable one-tap relief."*
- **Duration**: 45 seconds.
- **Recovery If Fails**: If frontend does not load, verify dev server is running on port 8000.

---

### Step 2: Voice Note Ingestion (0:45 – 1:30)
- **What to Click**: Click on the voice recording microphone button OR click **Upload Audio** and select `backend/tests/fixtures/voice_notes/en_01_bank_impersonation.wav` (or Hindi `hi_01_bank_otp.wav`).
- **What Appears on Screen**: Audio waveform/preview displays duration (under 120s) and file size (< 5MB). Progress bar indicates upload acceptance.
- **Speaking Script**:
  > *"The victim simply clicks record or uploads a voice note. Saathi AI enforces strict security: audio is capped at 5 megabytes and 120 seconds, and validated at the binary layer with PyAV against malicious containers and decompression bombs. The audio is queued with a cryptographically secure token."*
- **Duration**: 45 seconds.

---

### Step 3: Local Transcription & Dialect Preservation (1:30 – 2:30)
- **What Appears on Screen**: Upload finishes, status updates to 'Completed'. The original language is displayed:
  - Language: **Hindi / Tamil / English** with confidence percentage.
  - Transcript appears in full native script.
  - Click **Translate into English** button: natural English translation appears side-by-side while preserving the original.
- **Speaking Script**:
  > *"Notice that Faster-Whisper runs 100% locally on the device—no voice audio is ever uploaded to proprietary cloud APIs. The model preserves the user's native script. If the victim spoke in Hindi, it displays Devanagari; if in Tamil, native Tamil script. For cross-state complaints or bank officials, our local translation engine generates a clear English translation with a single tap."*
- **Duration**: 60 seconds.

---

### Step 4: Structured Complaint Extraction (2:30 – 3:30)
- **What Appears on Screen**: Automatically transitions or redirects to `/c/{token}` (Review Page).
  - Incident Type: *Bank Impersonation*
  - Reported Entity: *Apex Union Bank*
  - Financial Loss: *₹15,000*
  - Phone Number: *Pre-filled or marked null*
  - Missing fields clearly labeled: *Incident Date: Not provided*.
  - Reference number generated: `SAI-XXXXXX`.
- **Speaking Script**:
  > *"Here, our local Qwen3 model extracts structured complaint fields. Notice two critical security guarantees: First, ZERO HALLUCINATION. The caller never mentioned an incident date, so Saathi AI correctly leaves it as null rather than inventing one. Second, CREDENTIAL REDACTION: The one-time password spoken in the audio was automatically scrubbed as [REDACTED], ensuring secrets are never persisted in complaints, logs, or PDFs."*
- **Duration**: 60 seconds.

---

### Step 5: Review & Explicit Confirmation (3:30 – 4:15)
- **What to Click**:
  1. Click **Edit Details**.
  2. Modify description or add notes: e.g., *"Caller spoke aggressively and pressured me."*
  3. Click **Save Changes**.
  4. Click **Confirm Complaint**.
- **What Appears on Screen**:
  - Modal confirms victim consent.
  - Status transitions from `awaiting_review` to `confirmed`.
  - The section **"Next Steps: Protect Yourself and Report the Incident"** unlocks!
- **Speaking Script**:
  > *"In Saathi AI, the victim remains in total control. No reporting action can ever be triggered while the complaint is in draft or review. Once the victim reviews the facts and clicks Confirm, the complaint is cryptographically sealed, an immutable audit event is recorded, and the one-tap relief actions are unlocked."*
- **Duration**: 45 seconds.

---

### Step 6: Post-Confirmation Reporting Assistance (4:15 – 5:15)
- **What to Click & Show**:
  1. **Notify My Bank**: Opens `mailto:` client with subject and structured body pre-filled with transaction particulars and account freeze request.
  2. **Call Helpline 1930**: Opens device dialler with `tel:1930` pre-dialled without auto-initiating calls.
  3. **Download Complaint PDF**: Downloads `SAI-XXXXXX-complaint.pdf`. Open and view: formal cybercrime layout, watermark, QR/reference code, redacted sensitive details, and legal citizen disclaimer.
  4. **Copy Cybercrime Portal Filing Steps**: Copies structured filing text to clipboard with a toast notification and direct link to `https://cybercrime.gov.in`.
- **Speaking Script**:
  > *"The golden hour after a cyber scam is critical for freezing funds. Saathi AI equips the citizen with four immediate actions:
  > One, a pre-filled bank freeze notice ready to email the bank branch.
  > Two, an instant bridge to the National Cybercrime Helpline 1930.
  > Three, a court-ready, professionally styled Complaint Summary PDF.
  > And four, one-click copied answers aligned directly with the National Cyber Crime Reporting Portal."*
- **Duration**: 60 seconds.

---

### Step 7: Simulated FIR Demonstration (5:15 – 5:45)
- **What to Click**: Click **Simulated FIR (Demo Mode)**.
- **What Appears on Screen**:
  - Prominent persistent warning banner: `⚠️ DEMO MODE: Simulated Police FIR Demonstration Only. Does NOT contact law enforcement or submit official records.`
  - Structured legal draft containing IPC / IT Act sections (e.g. 66D IT Act, 420 IPC), incident narrative, and police station jurisdiction placeholder.
- **Speaking Script**:
  > *"For presentation and educational purposes, we provide a Simulated FIR generator. As you can see, this is prominently watermarked with a persistent Demo Mode banner. Saathi AI never deceives citizens: it clearly distinguishes genuine application actions from demonstration simulations."*
- **Duration**: 30 seconds.

---

### Step 8: Public Helpline Status Lookup (5:45 – 6:15)
- **What to Click**: Navigate to `/helpline` (or click Track Complaint Status).
  - Enter the reference number: `SAI-XXXXXX`.
  - Click **Track Status**.
- **What Appears on Screen**: Displays status badge (`CONFIRMED`), submission timestamp, and timeline of recorded events. Private loss details and victim identity are withheld.
- **Speaking Script**:
  > *"Any citizen or helpline operator can verify progress at `/helpline` using their reference number. To protect privacy, this public endpoint discloses only high-level status and timeline events, protected by strict IP rate limiting."*
- **Duration**: 30 seconds.

---

### Step 9: Security & Privacy Wrap-Up (6:15 – 7:00)
- **Speaking Script**:
  > *"To summarize: Saathi AI is built on four core pillars:
  > 1. Privacy-first local AI: Faster-Whisper and Qwen3 run entirely on-premise without third-party API exposure.
  > 2. Zero raw audio retention: Temporary recordings are deleted immediately upon transcription.
  > 3. Zero invented facts: Rigorously benchmarked against synthetic datasets.
  > 4. Victim empowerment: Bridging linguistic diversity to fight cybercrime across Bharat.
  > Thank you!"*
- **Duration**: 45 seconds.

---

## Demo Fallback & Recovery Matrix

| Potential Glitch | Immediate Recovery Action |
|---|---|
| **Microphone permission blocked in browser** | Switch to the Upload tab and select `backend/tests/fixtures/voice_notes/en_01_bank_impersonation.wav`. |
| **Ollama model taking >15s** | The built-in 3-step retry and automated fallback summary will kick in automatically without UI crash. |
| **Accidental page refresh** | The token is stored in `localStorage` and URL query; page restores state immediately upon reload. |
| **Network outage during presentation** | The app runs 100% on localhost (`127.0.0.1`); continue demo uninterrupted. |
| **Hardware failure / presentation laptop freeze** | Play the pre-recorded offline backup demo video (`demo_backup_recording.webm`). |
