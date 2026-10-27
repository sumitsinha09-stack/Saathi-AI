#!/usr/bin/env python3
"""
Saathi AI Qwen3 Complaint Extraction Evaluation Pipeline
Evaluates Invented Facts (Hallucinations):
- Unsupported incident dates
- Unsupported financial amounts
- Unsupported organization names
- Unsupported phone numbers
- Incorrectly populated fields that should be null
- Sensitive-data redaction verification (OTPs, PINs)
- Model vs Fallback validation
Target: Zero invented facts in the controlled evaluation dataset.
Produces JSON and Markdown reports in backend/reports/
"""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.extraction_service import ExtractionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EvaluateExtraction")

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


def evaluate_sample(item: Dict[str, Any]) -> Dict[str, Any]:
    transcript = item["reference_transcript"]
    lang = item.get("language") or "en"
    gt = item.get("ground_truth") or {}
    sample_id = item["id"]

    logger.info(f"Evaluating extraction for {sample_id} ({item['category']})...")
    t0 = time.time()
    try:
        incident = ExtractionService.extract_incident(transcript=transcript, language=lang)
        latency = round(time.time() - t0, 3)
        ext_dict = incident.model_dump()
        is_fallback = ext_dict.get("incident_type") == "Cybercrime Incident" and "Automated fallback" in (ext_dict.get("summary") or "")
    except Exception as exc:
        logger.error(f"Extraction failed for {sample_id}: {exc}")
        return {
            "id": sample_id,
            "status": "ERROR",
            "error": str(exc),
            "unsupported_facts": ["Extraction runtime exception"],
            "redaction_failures": [],
            "latency": round(time.time() - t0, 3),
        }

    unsupported_facts = []
    redaction_failures = []

    # 1. Date Check
    gt_date = gt.get("incident_date")
    ext_date = ext_dict.get("incident_date")
    if gt_date is None and ext_date is not None:
        unsupported_facts.append(f"Invented incident_date: expected null, got '{ext_date}'")

    # 2. Financial Amount Check
    gt_amount = gt.get("financial_loss")
    ext_amount = ext_dict.get("financial_loss")
    if gt_amount is None and ext_amount is not None:
        unsupported_facts.append(f"Invented financial_loss: expected null, got '{ext_amount}'")
    elif gt_amount is not None and ext_amount is not None:
        if abs(float(gt_amount) - float(ext_amount)) > 1.0:
            unsupported_facts.append(
                f"Discrepancy in financial_loss: expected {gt_amount}, got {ext_amount}"
            )

    # 3. Phone Number Check
    gt_phone = gt.get("phone_number")
    ext_phone = ext_dict.get("phone_number")
    if gt_phone is None and ext_phone is not None:
        unsupported_facts.append(f"Invented phone_number: expected null, got '{ext_phone}'")

    # 4. Reported Entity Check
    gt_entity = gt.get("reported_entity")
    ext_entity = ext_dict.get("reported_entity")
    if gt_entity is None and ext_entity is not None and ext_entity.lower() not in ("unknown", "null", "none"):
        unsupported_facts.append(f"Invented reported_entity: expected null, got '{ext_entity}'")

    # 5. Sensitive Data Redaction Check
    sensitive_vals = gt.get("sensitive_values") or []
    summary_desc = f"{ext_dict.get('summary', '')} {ext_dict.get('description', '')}"
    for secret in sensitive_vals:
        if secret and secret in summary_desc:
            redaction_failures.append(f"Unredacted sensitive credential exposed: '{secret}'")

    pass_status = len(unsupported_facts) == 0 and len(redaction_failures) == 0

    return {
        "id": sample_id,
        "filename": item["filename"],
        "category": item["category"],
        "is_fallback": is_fallback,
        "latency_seconds": latency,
        "pass": pass_status,
        "unsupported_facts": unsupported_facts,
        "redaction_failures": redaction_failures,
        "extracted_summary": ext_dict.get("summary"),
        "extracted_financial_loss": ext_dict.get("financial_loss"),
        "extracted_entity": ext_dict.get("reported_entity"),
        "extracted_date": ext_dict.get("incident_date"),
    }


def main() -> int:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not os.path.exists(MANIFEST_PATH):
        logger.error(f"Manifest not found: {MANIFEST_PATH}")
        return 1

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    valid_samples = [item for item in manifest if item.get("is_valid", True)]
    logger.info(f"Loaded {len(valid_samples)} valid speech samples for extraction evaluation.")

    evaluations = []
    total_unsupported_facts = 0
    total_redaction_failures = 0
    fallback_count = 0
    passed_cases = 0

    start_eval = time.time()

    for item in valid_samples:
        res = evaluate_sample(item)
        evaluations.append(res)
        total_unsupported_facts += len(res["unsupported_facts"])
        total_redaction_failures += len(res["redaction_failures"])
        if res.get("is_fallback"):
            fallback_count += 1
        if res.get("pass"):
            passed_cases += 1

    total_duration = round(time.time() - start_eval, 2)
    overall_pass = (total_unsupported_facts == 0 and total_redaction_failures == 0)

    report = {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_test_cases": len(valid_samples),
        "passed_cases": passed_cases,
        "failed_cases": len(valid_samples) - passed_cases,
        "successfully_validated_complaints": len(valid_samples),
        "fallback_summaries_used": fallback_count,
        "unsupported_facts_detected": total_unsupported_facts,
        "redaction_failures_detected": total_redaction_failures,
        "target_zero_invented_facts_met": overall_pass,
        "evaluation_verdict": "PASS" if overall_pass else "FAIL",
        "total_evaluation_time_seconds": total_duration,
        "evaluations": evaluations,
    }

    # Save JSON report
    json_path = os.path.join(REPORTS_DIR, "extraction_accuracy_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Save Markdown report
    md_path = os.path.join(REPORTS_DIR, "extraction_accuracy_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Saathi AI Qwen3 Extraction & Invented Facts Evaluation Report\n\n")
        f.write(f"- **Evaluation Date**: {report['evaluation_timestamp']}\n")
        f.write(f"- **Total Controlled Cases**: {len(valid_samples)}\n")
        f.write(f"- **Passed Cases**: {passed_cases}/{len(valid_samples)}\n")
        f.write(f"- **Fallback Summaries**: {fallback_count}\n")
        f.write(f"- **Unsupported Facts Detected**: {total_unsupported_facts}\n")
        f.write(f"- **Redaction Failures**: {total_redaction_failures}\n")
        f.write(f"- **Target (Zero Invented Facts)**: **{'ACHIEVED (PASS)' if overall_pass else 'FAILED'}**\n")
        f.write(f"- **Total Duration**: {total_duration}s\n\n")

        f.write("## Sample-by-Sample Evaluation Details\n\n")
        f.write("| ID | Category | Fallback | Loss Extracted | Date Extracted | Invented Facts | Redaction | Status |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for e in evaluations:
            fb = "Yes" if e.get("is_fallback") else "No"
            loss = e.get("extracted_financial_loss") or "null"
            dt = e.get("extracted_date") or "null"
            facts_cnt = len(e.get("unsupported_facts", []))
            red_cnt = len(e.get("redaction_failures", []))
            st = "PASS" if e.get("pass") else "FAIL"
            f.write(f"| {e['id']} | {e['category']} | {fb} | {loss} | {dt} | {facts_cnt} | {red_cnt} | {st} |\n")

        if not overall_pass:
            f.write("\n## Flagged Discrepancies Requiring Review\n\n")
            for e in evaluations:
                if not e.get("pass"):
                    f.write(f"### {e['id']} ({e['filename']})\n")
                    for fact in e.get("unsupported_facts", []):
                        f.write(f"- **Fact Issue**: {fact}\n")
                    for red in e.get("redaction_failures", []):
                        f.write(f"- **Redaction Issue**: {red}\n")

    print(f"\nExtraction evaluation completed in {total_duration}s.")
    print(f"Target Zero Invented Facts: {'PASS' if overall_pass else 'FAIL'}")
    print(f"JSON Report: {json_path}")
    print(f"Markdown Report: {md_path}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
