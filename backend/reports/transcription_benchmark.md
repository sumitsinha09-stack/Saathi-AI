# Saathi AI Faster-Whisper Transcription Benchmark Report

- **Benchmark Date**: 2026-10-27T00:11:41Z
- **Total Evaluated Cases**: 20
- **Valid Speech Samples**: 16
- **Negative Rejection Test Cases**: 4
- **Overall Language Detection Accuracy**: 100.0%
- **Negative Sample Rejection Rate**: 75.0%
- **Total Execution Latency**: 476.54s

## Category Performance Summary

| Category | Samples | Avg WER | Avg CER | Language Accuracy | Rejection Rate |
|---|---|---|---|---|---|
| English speech | 4 | 16.1% | 4.0% | 100.0% | N/A |
| Hindi speech | 4 | 27.4% | 19.5% | 100.0% | N/A |
| Tamil speech | 4 | 16.5% | 14.1% | 100.0% | N/A |
| Accent variation | 2 | 14.5% | 6.6% | 100.0% | N/A |
| Background noise | 2 | 24.7% | 16.3% | 100.0% | N/A |
| Empty or silent audio | 1 | N/A | N/A | N/A | 0.0% |
| Excessively long audio | 1 | N/A | N/A | N/A | 100.0% |
| Unsupported or malformed audio | 2 | N/A | N/A | N/A | 100.0% |

## Detailed Sample Results

| ID | File | Category | Exp Lang | Det Lang | WER | CER | Status |
|---|---|---|---|---|---|---|---|
| en_01 | `en_01_bank_impersonation.wav` | English speech | en | en | 28.1% | 10.1% | PASS |
| en_02 | `en_02_kyc_freeze.wav` | English speech | en | en | 26.7% | 5.9% | PASS |
| en_03 | `en_03_lottery_scam.wav` | English speech | en | en | 4.5% | 0.0% | PASS |
| en_04 | `en_04_courier_fraud.wav` | English speech | en | en | 4.9% | 0.0% | PASS |
| hi_01 | `hi_01_bank_otp.wav` | Hindi speech | hi | hi | 21.6% | 14.3% | PASS |
| hi_02 | `hi_02_electricity_bill.wav` | Hindi speech | hi | hi | 33.3% | 20.7% | PASS |
| hi_03 | `hi_03_instant_loan.wav` | Hindi speech | hi | hi | 26.1% | 21.9% | PASS |
| hi_04 | `hi_04_part_time_job.wav` | Hindi speech | hi | hi | 28.6% | 20.9% | PASS |
| ta_01 | `ta_01_bank_block.wav` | Tamil speech | ta | ta | 20.6% | 14.7% | PASS |
| ta_02 | `ta_02_kyc_warning.wav` | Tamil speech | ta | ta | 7.8% | 3.6% | PASS |
| ta_03 | `ta_03_customs_parcel.wav` | Tamil speech | ta | ta | 20.3% | 20.6% | PASS |
| ta_04 | `ta_04_prize_scam.wav` | Tamil speech | ta | ta | 17.5% | 17.4% | PASS |
| accent_01 | `accent_01_indian_english_speed.wav` | Accent variation | en | en | 23.5% | 11.3% | PASS |
| accent_02 | `accent_02_fast_hinglish.wav` | Accent variation | en | en | 5.6% | 1.8% | PASS |
| noise_01 | `noise_01_traffic_english.wav` | Background noise | en | en | 20.8% | 7.1% | PASS |
| noise_02 | `noise_02_cafe_hindi.wav` | Background noise | hi | hi | 28.6% | 25.5% | PASS |
| neg_01 | `neg_01_silent.wav` | Empty or silent audio | N/A | N/A | N/A | N/A | FAILED_TO_REJECT |
| neg_02 | `neg_02_too_long.wav` | Excessively long audio | N/A | N/A | N/A | N/A | REJECTED (PASS) |
| neg_03 | `neg_03_corrupted_header.wav` | Unsupported or malformed audio | N/A | N/A | N/A | N/A | REJECTED (PASS) |
| neg_04 | `neg_04_bad_codec.wav` | Unsupported or malformed audio | N/A | N/A | N/A | N/A | REJECTED (PASS) |


*Note: This synthetic speech evaluation provides reproducible baselines for the deployed models and decoder configurations; it is not a claim of universal real-world speech coverage.*