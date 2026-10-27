# Saathi AI — Feature Classification & Operational Scope

This document provides a transparent, legally accurate classification of genuine application functionality versus demonstration simulations and out-of-scope integrations.

---

## Operational Status Matrix

| Feature / Capability | Classification | Operational Description & Safeguards |
|---|---|---|
| **Browser Voice Recording & Audio Upload** | **Real Application Functionality** | Captures microphone input via HTML5 MediaRecorder API or accepts uploaded audio files (`.wav`, `.webm`, `.mp3`, `.ogg`, `.m4a`). |
| **Strict Audio Validation & Spool Management** | **Real Application Functionality** | Enforces 5 MB size limit, 120-second duration limit, magic byte validation, and PyAV deep-stream decodability checks. Safely cleans temporary spool files. |
| **Faster-Whisper Speech Transcription** | **Real Local Processing** | Runs on-premise Faster-Whisper model. Preserves native language script (Devanagari for Hindi, Tamil script for Tamil, Latin script for English). |
| **Optional English Speech Translation** | **Real Local Processing** | Translates regional transcripts into English using local inference models or translation engines without cloud leaks. |
| **Qwen3 Structured Complaint Extraction** | **Real Local Processing** | Extracts structured cybercrime incident fields via local Ollama inference with prompt constraints enforcing null for unmentioned facts. |
| **Sensitive Credential Redaction** | **Real Application Functionality** | Centralized `RedactionService` scrubs OTPs, CVVs, passwords, PINs, and full card numbers before persistence, logging, or PDF generation. |
| **Pydantic Schema Validation** | **Real Application Functionality** | Enforces data integrity and strict types on all complaint fields and updates. |
| **Complaint Reference Number Generation** | **Real Application Functionality** | Generates non-sequential reference identifiers in `SAI-XXXXXX` format with cryptographic verification tokens. |
| **Victim Review, Field Editing & Confirmation** | **Real Application Functionality** | Interactive review interface allows editing, correcting, confirming, or cancelling complaints before locking audit status. |
| **PDF Complaint Summary Generation** | **Real Application Functionality** | Generates formal, mobile-friendly PDF summaries using ReportLab with citizen disclaimers and status history. |
| **Pre-filled Bank Notification Email** | **Email Composition Only** | Generates structured `mailto:` payload pre-filled with victim incident details. Actual transmission depends entirely on the user's local email client. |
| **Helpline 1930 Action** | **Dialler Link Only** | Invokes `tel:1930` on mobile devices. Does not automatically dial or establish that a telecom call has connected. |
| **Cybercrime Portal Guidance** | **Informational Assistance** | Copies aligned incident details and step-by-step instructions to clipboard. The citizen files the complaint on `cybercrime.gov.in` separately. |
| **Public Reference Lookup (`/helpline`)** | **Real Application Functionality** | Allows citizen reference number verification, returning sanitized status and audit events while protecting private narratives. |
| **Simulated FIR Generator** | **Simulated Demonstration Only** | Educational demonstration of a First Information Report draft. Prominently labeled with a persistent Demo Mode banner; does NOT register complaints with state police. |
| **Direct Bank Account Freeze / Lien** | **Not Implemented** | Saathi AI does not hold direct banking API authority or NPCI integration to unilaterally freeze customer accounts. |
| **Direct Police FIR Registration** | **Not Implemented** | Saathi AI does not possess statutory authority to register FIRs under CrPC / BNSS without physical police station or portal filing. |
| **Automated Government Portal Submission** | **Not Implemented** | Does not bypass captcha or submit automated headless requests to the National Cyber Crime Reporting Portal. |
| **Fund Recovery Guarantee** | **Not Guaranteed / Simulated** | Recovery of lost money depends on bank fraud desks, nodal officers, and judicial process; Saathi AI provides rapid documentation, not fund recovery guarantees. |

---

## Citizen & Presentation Disclaimers

1. **Simulated FIR Disclaimer**:
   > *"The Simulated FIR generator is an educational demonstration tool. It does not file a formal complaint with the police or any government law enforcement agency. To file an official complaint, citizens must visit their local cyber police station or file on https://cybercrime.gov.in."*

2. **One-Tap Actions Disclaimer**:
   > *"Actions provided in Saathi AI (such as bank emails and 1930 links) assist the victim in initiating contact with authorized institutions during the golden hour. Saathi AI does not act as an intermediary, bank representative, or legal authority."*
