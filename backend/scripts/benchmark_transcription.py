#!/usr/bin/env python3
"""
Saathi AI Faster-Whisper Transcription Benchmark
Evaluates:
- Word Error Rate (WER)
- Character Error Rate (CER)
- Language Detection Accuracy
- Negative Sample Rejection Accuracy
Produces JSON and Markdown reports in backend/reports/
"""

import json
import logging
import os
import re
import sys
import time
import unicodedata
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.audio_validator import validate_and_save_audio
from backend.app.services.transcription_service import TranscriptionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BenchmarkTranscription")

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
    "voice_notes",
)
MANIFEST_PATH = os.path.join(FIXTURES_DIR, "manifest.json")
REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports",
)


def normalize_for_eval(text: str) -> str:
    """
    Evaluation-only Unicode normalization.
    Decomposes punctuation, strips whitespace, standardizes digits and casing.
    Does NOT modify the user-facing transcript.
    """
    if not text:
        return ""
    # Normalize to Unicode NFC
    norm = unicodedata.normalize("NFC", text).lower()
    # Remove punctuation
    norm = re.sub(r"[^\w\s]", " ", norm)
    # Collapse multiple whitespaces
    norm = " ".join(norm.split())
    return norm


def levenshtein_tokens(ref: List[str], hyp: List[str]) -> int:
    """Levenshtein distance at token list level."""
    m, n = len(ref), len(hyp)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def compute_wer(ref: str, hyp: str) -> float:
    ref_tokens = normalize_for_eval(ref).split()
    hyp_tokens = normalize_for_eval(hyp).split()
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    dist = levenshtein_tokens(ref_tokens, hyp_tokens)
    return min(1.0, round(dist / len(ref_tokens), 4))


def compute_cer(ref: str, hyp: str) -> float:
    ref_chars = list(normalize_for_eval(ref).replace(" ", ""))
    hyp_chars = list(normalize_for_eval(hyp).replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = levenshtein_tokens(ref_chars, hyp_chars)
    return min(1.0, round(dist / len(ref_chars), 4))


def main() -> int:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not os.path.exists(MANIFEST_PATH):
        logger.error(f"Manifest file not found at: {MANIFEST_PATH}")
        return 1

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"Loaded {len(manifest)} test fixtures from manifest.")

    results_by_category: Dict[str, List[Dict[str, Any]]] = {}
    lang_matches = 0
    total_valid = 0
    negative_rejected = 0
    total_negative = 0
    all_evaluations: List[Dict[str, Any]] = []

    start_bench = time.time()

    for item in manifest:
        file_path = os.path.join(FIXTURES_DIR, item["filename"])
        is_valid = item["is_valid"]
        cat = item["category"]

        if is_valid:
            total_valid += 1
            logger.info(f"Transcribing valid sample: {item['filename']} ({cat})...")
            t0 = time.time()
            trans_res = TranscriptionService.transcribe_audio(file_path=file_path)
            duration = round(time.time() - t0, 3)

            hyp_text = trans_res["transcript"]
            detected_lang = trans_res["language"]
            expected_lang = item["language"]
            ref_text = item["reference_transcript"]

            is_lang_correct = (detected_lang == expected_lang)
            if is_lang_correct:
                lang_matches += 1

            wer = compute_wer(ref_text, hyp_text)
            cer = compute_cer(ref_text, hyp_text)

            eval_entry = {
                "id": item["id"],
                "filename": item["filename"],
                "category": cat,
                "expected_language": expected_lang,
                "detected_language": detected_lang,
                "language_correct": is_lang_correct,
                "latency_seconds": duration,
                "wer": wer,
                "cer": cer,
                "ref_snippet": ref_text[:60] + "...",
                "hyp_snippet": hyp_text[:60] + "..." if hyp_text else "<EMPTY>",
            }
            results_by_category.setdefault(cat, []).append(eval_entry)
            all_evaluations.append(eval_entry)
        else:
            # Negative test case: verify rejection
            total_negative += 1
            logger.info(f"Evaluating negative sample rejection: {item['filename']} ({cat})...")
            rejected = False
            rejection_detail = ""

            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                # Test audio validation
                client_duration = 125.0 if "too_long" in item.get("special_type", "") else None
                validate_and_save_audio(
                    file_bytes=file_bytes,
                    content_type="audio/wav",
                    client_duration=client_duration,
                )
            except Exception as exc:
                rejected = True
                rejection_detail = str(exc)

            if rejected:
                negative_rejected += 1

            eval_entry = {
                "id": item["id"],
                "filename": item["filename"],
                "category": cat,
                "is_valid": False,
                "rejected_correctly": rejected,
                "expected_rejection": item.get("expected_rejection"),
                "actual_rejection_detail": rejection_detail,
            }
            results_by_category.setdefault(cat, []).append(eval_entry)
            all_evaluations.append(eval_entry)

    total_time = round(time.time() - start_bench, 2)

    # Category summaries
    cat_summary = {}
    for cat, entries in results_by_category.items():
        valid_entries = [e for e in entries if e.get("is_valid", True) and "wer" in e]
        if valid_entries:
            avg_wer = round(sum(e["wer"] for e in valid_entries) / len(valid_entries), 4)
            avg_cer = round(sum(e["cer"] for e in valid_entries) / len(valid_entries), 4)
            lang_acc = round(
                sum(1 for e in valid_entries if e["language_correct"]) / len(valid_entries),
                4,
            )
            cat_summary[cat] = {
                "samples_count": len(valid_entries),
                "avg_wer": avg_wer,
                "avg_cer": avg_cer,
                "language_detection_accuracy": lang_acc,
            }
        else:
            rejected_count = sum(1 for e in entries if e.get("rejected_correctly"))
            cat_summary[cat] = {
                "samples_count": len(entries),
                "rejection_accuracy": round(rejected_count / len(entries), 4),
            }

    lang_accuracy_overall = round(lang_matches / total_valid, 4) if total_valid else 0.0
    rejection_accuracy_overall = (
        round(negative_rejected / total_negative, 4) if total_negative else 1.0
    )

    report_data = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_test_cases": len(manifest),
        "valid_speech_cases": total_valid,
        "negative_test_cases": total_negative,
        "total_benchmark_time_seconds": total_time,
        "overall_language_detection_accuracy": lang_accuracy_overall,
        "overall_negative_rejection_accuracy": rejection_accuracy_overall,
        "category_summary": cat_summary,
        "detailed_results": all_evaluations,
    }

    # Write JSON report
    json_path = os.path.join(REPORTS_DIR, "transcription_benchmark.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    # Write Markdown summary
    md_path = os.path.join(REPORTS_DIR, "transcription_benchmark.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Saathi AI Faster-Whisper Transcription Benchmark Report\n\n")
        f.write(f"- **Benchmark Date**: {report_data['benchmark_timestamp']}\n")
        f.write(f"- **Total Evaluated Cases**: {report_data['total_test_cases']}\n")
        f.write(f"- **Valid Speech Samples**: {total_valid}\n")
        f.write(f"- **Negative Rejection Test Cases**: {total_negative}\n")
        f.write(f"- **Overall Language Detection Accuracy**: {lang_accuracy_overall * 100:.1f}%\n")
        f.write(f"- **Negative Sample Rejection Rate**: {rejection_accuracy_overall * 100:.1f}%\n")
        f.write(f"- **Total Execution Latency**: {total_time}s\n\n")

        f.write("## Category Performance Summary\n\n")
        f.write("| Category | Samples | Avg WER | Avg CER | Language Accuracy | Rejection Rate |\n")
        f.write("|---|---|---|---|---|---|\n")
        for cat, stats in cat_summary.items():
            samples = stats["samples_count"]
            wer_s = f"{stats.get('avg_wer', 0.0)*100:.1f}%" if "avg_wer" in stats else "N/A"
            cer_s = f"{stats.get('avg_cer', 0.0)*100:.1f}%" if "avg_cer" in stats else "N/A"
            lang_s = f"{stats.get('language_detection_accuracy', 0.0)*100:.1f}%" if "language_detection_accuracy" in stats else "N/A"
            rej_s = f"{stats.get('rejection_accuracy', 1.0)*100:.1f}%" if "rejection_accuracy" in stats else "N/A"
            f.write(f"| {cat} | {samples} | {wer_s} | {cer_s} | {lang_s} | {rej_s} |\n")

        f.write("\n## Detailed Sample Results\n\n")
        f.write("| ID | File | Category | Exp Lang | Det Lang | WER | CER | Status |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for e in all_evaluations:
            if e.get("is_valid", True) and "wer" in e:
                stat = "PASS" if e["language_correct"] else "LANG_MISMATCH"
                f.write(
                    f"| {e['id']} | `{e['filename']}` | {e['category']} | {e['expected_language']} | "
                    f"{e['detected_language']} | {e['wer']*100:.1f}% | {e['cer']*100:.1f}% | {stat} |\n"
                )
            else:
                stat = "REJECTED (PASS)" if e.get("rejected_correctly") else "FAILED_TO_REJECT"
                f.write(
                    f"| {e['id']} | `{e['filename']}` | {e['category']} | N/A | N/A | N/A | N/A | {stat} |\n"
                )

        f.write("\n\n*Note: This synthetic speech evaluation provides reproducible baselines for the deployed models and decoder configurations; it is not a claim of universal real-world speech coverage.*")

    print(f"\nBenchmark completed successfully in {total_time}s.")
    print(f"JSON Report: {json_path}")
    print(f"Markdown Report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
