#!/usr/bin/env python3
"""
Saathi AI End-to-End Processing Latency Benchmark
Measures stage-by-stage latencies:
- Audio validation latency
- Faster-Whisper transcription latency
- English translation latency
- Qwen3 complaint extraction latency
- Complaint & audit persistence latency
- Total upload-to-summary latency
Reports P50 (median), P95, and Max latencies, and writes JSON/Markdown reports to backend/reports/
"""

import asyncio
import json
import logging
import os
import platform
import sys
import time
from typing import Any, Dict, List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.config import settings
from backend.app.services.audio_validator import validate_and_save_audio
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.transcription_service import TranscriptionService
from backend.app.services.translation_service import TranslationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BenchmarkPerformance")

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

# Configurable warning threshold (seconds) for slow pipeline execution
SLOW_JOB_THRESHOLD_SECONDS = 30.0


def run_single_job(file_path: str, filename: str) -> Dict[str, Any]:
    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    # 1. Validation Latency
    t0 = time.perf_counter()
    validation = validate_and_save_audio(
        file_bytes=audio_bytes,
        content_type="audio/wav",
    )
    t_val = round(time.perf_counter() - t0, 4)

    saved_file = validation.file_path

    try:
        # 2. Transcription Latency
        t1 = time.perf_counter()
        trans_res = TranscriptionService.transcribe_audio(file_path=saved_file)
        t_trans = round(time.perf_counter() - t1, 4)
        transcript = trans_res["transcript"]
        lang = trans_res["language"]

        # 3. Translation Latency (if requested or non-English)
        t2 = time.perf_counter()
        trans_res = TranslationService.translate_transcript(
            text=transcript,
            source_language=lang,
        )
        t_translate = round(time.perf_counter() - t2, 4)

        # 4. Complaint Extraction Latency
        t3 = time.perf_counter()
        incident = ExtractionService.extract_incident(transcript=transcript, language=lang)
        t_extract = round(time.perf_counter() - t3, 4)

        # 5. Database / Storage Persistence Latency
        t4 = time.perf_counter()
        complaint = asyncio.run(
            ComplaintService.create_complaint(
                incident=incident,
                upload_token=validation.token,
            )
        )
        t_persist = round(time.perf_counter() - t4, 4)

        total_latency = round(t_val + t_trans + t_translate + t_extract + t_persist, 4)

        warning = total_latency > SLOW_JOB_THRESHOLD_SECONDS
        if warning:
            logger.warning(
                f"Job for {filename} exceeded warning threshold: {total_latency}s > {SLOW_JOB_THRESHOLD_SECONDS}s"
            )

        return {
            "filename": filename,
            "status": "success",
            "warning": warning,
            "validation_seconds": t_val,
            "transcription_seconds": t_trans,
            "translation_seconds": t_translate,
            "extraction_seconds": t_extract,
            "persistence_seconds": t_persist,
            "total_latency_seconds": total_latency,
            "reference_number": complaint.get("reference_number"),
        }

    finally:
        # Mandatory cleanup
        if os.path.exists(saved_file):
            try:
                os.remove(saved_file)
            except OSError:
                pass


def main() -> int:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not os.path.exists(MANIFEST_PATH):
        logger.error(f"Manifest not found: {MANIFEST_PATH}")
        return 1

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Select representative speech samples across languages
    speech_samples = [item for item in manifest if item.get("is_valid", True)][:6]
    logger.info(f"Running pipeline performance benchmark on {len(speech_samples)} speech samples...")

    job_results: List[Dict[str, Any]] = []
    successful_jobs = 0
    failed_jobs = 0

    for idx, item in enumerate(speech_samples, 1):
        file_path = os.path.join(FIXTURES_DIR, item["filename"])
        logger.info(f"[{idx}/{len(speech_samples)}] Measuring latency for: {item['filename']}...")
        try:
            res = run_single_job(file_path, item["filename"])
            job_results.append(res)
            successful_jobs += 1
        except Exception as e:
            logger.error(f"Job failed for {item['filename']}: {e}", exc_info=True)
            job_results.append({
                "filename": item["filename"],
                "status": "failed",
                "error": str(e),
            })
            failed_jobs += 1

    # Latency percentiles
    totals = [r["total_latency_seconds"] for r in job_results if r.get("status") == "success"]
    transcriptions = [r["transcription_seconds"] for r in job_results if r.get("status") == "success"]
    translations = [r["translation_seconds"] for r in job_results if r.get("status") == "success"]
    extractions = [r["extraction_seconds"] for r in job_results if r.get("status") == "success"]

    p50_total = round(float(np.percentile(totals, 50)), 3) if totals else 0.0
    p95_total = round(float(np.percentile(totals, 95)), 3) if totals else 0.0
    max_total = round(float(np.max(totals)), 3) if totals else 0.0

    p50_trans = round(float(np.percentile(transcriptions, 50)), 3) if transcriptions else 0.0
    p50_translat = round(float(np.percentile(translations, 50)), 3) if translations else 0.0
    p50_ext = round(float(np.percentile(extractions, 50)), 3) if extractions else 0.0

    hardware_info = {
        "os": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "whisper_model": settings.WHISPER_MODEL_SIZE,
        "whisper_device": settings.WHISPER_DEVICE,
        "whisper_compute": settings.WHISPER_COMPUTE_TYPE,
        "ollama_model": settings.OLLAMA_MODEL,
    }

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware_environment": hardware_info,
        "total_jobs_evaluated": len(speech_samples),
        "successful_jobs": successful_jobs,
        "failed_jobs": failed_jobs,
        "warning_threshold_seconds": SLOW_JOB_THRESHOLD_SECONDS,
        "latencies_summary": {
            "total_upload_to_summary": {
                "median_p50_seconds": p50_total,
                "p95_seconds": p95_total,
                "max_seconds": max_total,
            },
            "transcription_median_p50_seconds": p50_trans,
            "translation_median_p50_seconds": p50_translat,
            "extraction_median_p50_seconds": p50_ext,
        },
        "individual_runs": job_results,
    }

    json_path = os.path.join(REPORTS_DIR, "performance_benchmark.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    md_path = os.path.join(REPORTS_DIR, "performance_benchmark.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Saathi AI End-to-End Processing Performance Benchmark\n\n")
        f.write(f"- **Benchmark Date**: {report['timestamp']}\n")
        f.write(f"- **Hardware/OS**: {hardware_info['os']} ({hardware_info['processor']})\n")
        f.write(f"- **Whisper Model**: `{hardware_info['whisper_model']}` on `{hardware_info['whisper_device']}` ({hardware_info['whisper_compute']})\n")
        f.write(f"- **Extraction Model**: `{hardware_info['ollama_model']}` via Ollama\n")
        f.write(f"- **Completed Jobs**: {successful_jobs}/{len(speech_samples)}\n\n")

        f.write("## Overall Latency Summary (Upload → Confirmed Complaint Summary)\n\n")
        f.write("| Metric | Latency (seconds) |\n")
        f.write("|---|---|\n")
        f.write(f"| **Median Latency (P50)** | **{p50_total}s** |\n")
        f.write(f"| **95th Percentile (P95)** | **{p95_total}s** |\n")
        f.write(f"| **Maximum Observed Latency** | **{max_total}s** |\n")
        f.write(f"| Faster-Whisper Transcription (Median) | {p50_trans}s |\n")
        f.write(f"| Speech Translation (Median) | {p50_translat}s |\n")
        f.write(f"| Qwen3 Complaint Extraction (Median) | {p50_ext}s |\n\n")

        f.write("## Individual Job Latencies\n\n")
        f.write("| Sample | Validation | Transcribe | Translate | Extract | Persist | Total |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in job_results:
            if r.get("status") == "success":
                f.write(
                    f"| `{r['filename']}` | {r['validation_seconds']}s | {r['transcription_seconds']}s | "
                    f"{r['translation_seconds']}s | {r['extraction_seconds']}s | {r['persistence_seconds']}s | "
                    f"**{r['total_latency_seconds']}s** |\n"
                )
            else:
                f.write(f"| `{r['filename']}` | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |\n")

    print(f"\nPerformance benchmark completed.")
    print(f"P50 Total Latency: {p50_total}s | P95: {p95_total}s | Max: {max_total}s")
    print(f"JSON Report: {json_path}")
    print(f"Markdown Report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
