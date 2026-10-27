# Saathi AI Qwen3 Extraction & Invented Facts Evaluation Report

- **Evaluation Date**: 2026-10-27T00:18:26Z
- **Total Controlled Cases**: 16
- **Passed Cases**: 9/16
- **Fallback Summaries**: 0
- **Unsupported Facts Detected**: 7
- **Redaction Failures**: 1
- **Target (Zero Invented Facts)**: **FAILED**
- **Total Duration**: 388.69s

## Sample-by-Sample Evaluation Details

| ID | Category | Fallback | Loss Extracted | Date Extracted | Invented Facts | Redaction | Status |
|---|---|---|---|---|---|---|---|
| en_01 | English speech | No | 15000.0 | null | 0 | 1 | FAIL |
| en_02 | English speech | No | null | null | 0 | 0 | PASS |
| en_03 | English speech | No | 12500.0 | null | 0 | 0 | PASS |
| en_04 | English speech | No | null | null | 0 | 0 | PASS |
| hi_01 | Hindi speech | No | 10000.0 | null | 1 | 0 | FAIL |
| hi_02 | Hindi speech | No | 4500.0 | null | 0 | 0 | PASS |
| hi_03 | Hindi speech | No | 50000.0 | null | 1 | 0 | FAIL |
| hi_04 | Hindi speech | No | 2000.0 | null | 0 | 0 | PASS |
| ta_01 | Tamil speech | No | null | null | 0 | 0 | PASS |
| ta_02 | Tamil speech | No | null | null | 1 | 0 | FAIL |
| ta_03 | Tamil speech | No | null | null | 0 | 0 | PASS |
| ta_04 | Tamil speech | No | 100000.0 | null | 2 | 0 | FAIL |
| accent_01 | Accent variation | No | 499.0 | null | 0 | 0 | PASS |
| accent_02 | Accent variation | No | null | null | 1 | 0 | FAIL |
| noise_01 | Background noise | No | 8400.0 | null | 0 | 0 | PASS |
| noise_02 | Background noise | No | null | null | 1 | 0 | FAIL |

## Flagged Discrepancies Requiring Review

### en_01 (en_01_bank_impersonation.wav)
- **Redaction Issue**: Unredacted sensitive credential exposed: '4821'
### hi_01 (hi_01_bank_otp.wav)
- **Fact Issue**: Invented phone_number: expected null, got '529418'
### hi_03 (hi_03_instant_loan.wav)
- **Fact Issue**: Discrepancy in financial_loss: expected 999.0, got 50000.0
### ta_02 (ta_02_kyc_warning.wav)
- **Fact Issue**: Invented reported_entity: expected null, got 'Bank'
### ta_04 (ta_04_prize_scam.wav)
- **Fact Issue**: Discrepancy in financial_loss: expected 10000.0, got 100000.0
- **Fact Issue**: Invented reported_entity: expected null, got 'மெகா பம்பர்'
### accent_02 (accent_02_fast_hinglish.wav)
- **Fact Issue**: Invented reported_entity: expected null, got 'Bank'
### noise_02 (noise_02_cafe_hindi.wav)
- **Fact Issue**: Invented reported_entity: expected null, got 'Bank'
