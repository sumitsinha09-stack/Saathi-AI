# Saathi AI End-to-End Processing Performance Benchmark

- **Benchmark Date**: 2026-10-27T00:28:36Z
- **Hardware/OS**: macOS-26.5-arm64-arm-64bit-Mach-O (arm)
- **Whisper Model**: `medium` on `cpu` (int8)
- **Extraction Model**: `qwen3:8b` via Ollama
- **Completed Jobs**: 6/6

## Overall Latency Summary (Upload → Confirmed Complaint Summary)

| Metric | Latency (seconds) |
|---|---|
| **Median Latency (P50)** | **29.494s** |
| **95th Percentile (P95)** | **85.793s** |
| **Maximum Observed Latency** | **86.304s** |
| Faster-Whisper Transcription (Median) | 15.535s |
| Speech Translation (Median) | 0.002s |
| Qwen3 Complaint Extraction (Median) | 14.02s |

## Individual Job Latencies

| Sample | Validation | Transcribe | Translate | Extract | Persist | Total |
|---|---|---|---|---|---|---|
| `en_01_bank_impersonation.wav` | 0.0193s | 18.724s | 0.0035s | 13.9336s | 0.023s | **32.7034s** |
| `en_02_kyc_freeze.wav` | 0.0496s | 12.3461s | 0.0001s | 13.8823s | 0.0057s | **26.2838s** |
| `en_03_lottery_scam.wav` | 0.0125s | 8.9041s | 0.0s | 14.106s | 0.0028s | **23.0254s** |
| `en_04_courier_fraud.wav` | 0.0131s | 9.211s | 0.0001s | 11.7847s | 0.0018s | **21.0107s** |
| `hi_01_bank_otp.wav` | 0.0109s | 35.8151s | 9.4095s | 41.0513s | 0.0175s | **86.3043s** |
| `hi_02_electricity_bill.wav` | 0.0388s | 36.7925s | 8.808s | 38.6108s | 0.0089s | **84.259s** |
