"""Four-engine, same-image OCR + evidence-gated safety evaluation.

This benchmark distinguishes transcription evidence from clinical classification.
Abstentions are reported as missing coverage; they are NEVER counted as negative
overdose or age-check predictions. No fabricated human verification is permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from medsafe.evaluation import evaluate
from medsafe.extraction import (
    extract_prescription, number_and_unit, parse_age, parse_frequency,
)
from medsafe.ocr_product import OCRUnavailable, recognize
from medsafe.preprocessing import MODES, prepare_ocr_bytes

ENGINES = ("tesseract", "easyocr", "paddleocr", "craft_trocr")


def read_manifest(manifest: Path, *, require_human=True):
    """Load independent image references before any OCR predictions exist."""
    root = Path(manifest).resolve().parent
    rows = []
    for index, line in enumerate(Path(manifest).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Manifest line {index}: invalid JSON") from exc
        if not isinstance(row, dict) or not row.get("image_path") or not row.get("image_id"):
            raise ValueError(f"Manifest line {index}: image_path and image_id are required")
        location = (root / str(row["image_path"])).resolve()
        if not location.is_relative_to(root):
            raise ValueError(f"Manifest line {index}: image path escapes manifest directory")
        if not location.is_file():
            raise ValueError(f"Manifest line {index}: image not found")
        if location.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError(f"Manifest line {index}: unsupported image format")
        if not isinstance(row.get("gold_transcript"), str) or not row["gold_transcript"].strip():
            raise ValueError(f"Manifest line {index}: nonempty gold_transcript required")
        if not isinstance(row.get("gold"), dict):
            raise ValueError(f"Manifest line {index}: gold field dictionary required")
        if require_human:
            if (
                row.get("human_verified") is not True
                or row.get("split") != "test"
                or not isinstance(row.get("reviewer_id"), str)
                or not row["reviewer_id"].strip()
            ):
                raise ValueError(
                    f"Manifest line {index}: held-out human-verification gate failed"
                )
        raw = location.read_bytes()
        rows.append({
            **row, "_path": str(location),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    if not rows:
        raise ValueError("No labeled image rows in manifest")
    ids = [row["image_id"] for row in rows]
    hashes = [row["sha256"] for row in rows]
    if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
        raise ValueError("Duplicate image IDs or identical image files in manifest")
    return rows


def _timing_stats(seconds):
    if not seconds:
        return {"n": 0, "mean_s": None, "median_s": None, "p95_s": None, "max_s": None}
    ordered = sorted(seconds)
    return {
        "n": len(ordered), "mean_s": round(statistics.mean(ordered), 4),
        "median_s": round(statistics.median(ordered), 4),
        "p95_s": round(ordered[math.ceil(.95 * len(ordered)) - 1], 4),
        "max_s": round(ordered[-1], 4),
    }


def _synthetic_screen(fields, rule):
    """Fictitious constant thresholds; available ONLY in synthetic development mode."""
    med = str(fields.get("medicine") or "").strip().upper()
    parsed = number_and_unit(fields.get("dose", ""))
    frequency = parse_frequency(fields.get("frequency", ""))
    age = parse_age(fields.get("age", ""))
    dose_flag = None
    age_flag = None
    if med.startswith("SYNTHMED-") and parsed is not None and parsed[1] == "mg" and frequency:
        if isinstance(rule, dict):
            single = rule.get("max_single_mg")
            daily = rule.get("max_daily_mg")
            if type(single) in (int, float) and type(daily) in (int, float):
                dose_flag = parsed[0] > single or parsed[0] * frequency > daily
    if med.startswith("SYNTHMED-") and age is not None and 0 <= age <= 120:
        if isinstance(rule, dict):
            minimum = rule.get("min_age_years")
            maximum = rule.get("max_age_years")
            if type(minimum) in (int, float) and type(maximum) in (int, float):
                age_flag = not minimum <= age <= maximum
    return dose_flag, age_flag


def _reviewed_screen(text):
    """Calculate flags only for exact, source-reviewed rules with complete context."""
    from backend.app.services.review_service import assess_report
    from medsafe.pipeline import analyze_text

    reviewed = assess_report(analyze_text(text, ocr_mode=True, with_references=False))
    medicines = reviewed.get("medications", [])
    if not medicines:
        return None, None
    dose_states = [med.get("reviewed_dose_rule", {}).get("status") for med in medicines]
    age_states = [med.get("reviewed_age_rule", {}).get("status") for med in medicines]
    dose_known = all(state in (
        "REVIEW_THRESHOLD_EXCEEDED", "BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY"
    ) for state in dose_states)
    age_known = all(state in (
        "REVIEW_AGE_RANGE_FLAG", "WITHIN_REVIEWED_AGE_RANGE_NOT_PROOF_OF_SAFETY"
    ) for state in age_states)
    return (
        any(state == "REVIEW_THRESHOLD_EXCEEDED" for state in dose_states) if dose_known else None,
        any(state == "REVIEW_AGE_RANGE_FLAG" for state in age_states) if age_known else None,
    )


def run_benchmark(manifest, *, engines=ENGINES, require_human=True, preprocess="none"):
    """Compute complete OCR and separately covered safety scores, never invented labels."""
    rows = read_manifest(Path(manifest), require_human=require_human)
    chosen = list(engines)
    if not chosen or len(set(chosen)) != len(chosen) or any(x not in ENGINES for x in chosen):
        raise ValueError("Choose one or more unique supported OCR engines")
    if preprocess not in MODES:
        raise ValueError("Unknown image preprocessing mode")
    output = {
        "schema": "medsafe.ocr_benchmark.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(Path(manifest).resolve()),
        "dataset_size": len(rows), "preprocessing_mode": preprocess,
        "label_policy": (
            "HUMAN_VERIFIED_TEST_ONLY" if require_human
            else "SYNTHETIC_DEVELOPMENT_ONLY_NOT_THESIS_EVIDENCE"
        ),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
        "engines": {},
    }
    for engine in chosen:
        records = []
        samples = []
        latencies = []
        failures = []
        for item in rows:
            try:
                start = time.perf_counter()
                original = Path(item["_path"]).read_bytes()
                model_input, preparation = prepare_ocr_bytes(original, mode=preprocess)
                recognized = recognize(model_input, engine=engine)
                text = str(recognized.get("text") or "")
                blocks = extract_prescription(text, allow_unlabeled=True)
                extracted = blocks[0]["fields"] if blocks else {}
                # Multi-drug prescriptions must not be silently scored as if
                # the first medication represented the entire prescription.
                if len(blocks) > 1:
                    extracted = dict(extracted)
                    extracted["medicine"] = " | ".join(
                        str(block["fields"].get("medicine", "")) for block in blocks
                    )
                if require_human:
                    dose_flag, age_flag = _reviewed_screen(text)
                else:
                    dose_flag, age_flag = _synthetic_screen(
                        blocks[0]["fields"] if blocks else {}, item.get("synthetic_rule")
                    )
                elapsed = time.perf_counter() - start
                rec = {
                    "gold": item["gold"], "predicted": extracted,
                    "gold_transcript": item["gold_transcript"],
                    "predicted_transcript": text,
                    "elapsed_seconds": elapsed,
                }
                if type(dose_flag) is bool and type(item.get("gold_alert")) is bool:
                    rec["gold_alert"] = item["gold_alert"]
                    rec["predicted_alert"] = dose_flag
                if type(age_flag) is bool and type(item.get("gold_age_flag")) is bool:
                    rec["gold_age_flag"] = item["gold_age_flag"]
                    rec["predicted_age_flag"] = age_flag
                records.append(rec)
                latencies.append(elapsed)
                samples.append({
                    "image_id": item["image_id"], "sha256": item["sha256"],
                    "engine": engine, "transcription": text, "fields": extracted,
                    "elapsed_seconds": round(elapsed, 5),
                    "dose_screen": "FLAG" if dose_flag is True else "BELOW_REVIEWED_THRESHOLD" if dose_flag is False else "ABSTAIN",
                    "age_screen": "FLAG" if age_flag is True else "WITHIN_REVIEWED_AGE_RANGE" if age_flag is False else "ABSTAIN",
                    "preprocessing": preparation,
                    "warnings": recognized.get("warnings", []),
                })
            except (OCRUnavailable, ImportError, RuntimeError, ValueError, FileNotFoundError) as exc:
                failures.append({
                    "image_id": item["image_id"], "type": type(exc).__name__,
                    "message": str(exc)[:260],
                })
        complete = len(records) == len(rows) and not failures
        metrics = evaluate(records) if complete else None
        dose_coverage = metrics["alerts"]["n"] if metrics else 0
        age_coverage = metrics["age_alerts"]["n"] if metrics else 0
        output["engines"][engine] = {
            "n_total": len(rows), "n_succeeded": len(records),
            "coverage": round(len(records) / len(rows), 6),
            "preprocessing_mode": preprocess,
            "timing": _timing_stats(latencies),
            "metrics": metrics, "ocr_eligible": bool(complete and require_human),
            "dose_alert_evaluated_n": dose_coverage,
            "age_alert_evaluated_n": age_coverage,
            "thesis_eligible": bool(
                complete and require_human and len(rows) >= 50
                and dose_coverage == len(rows) and age_coverage == len(rows)
                and metrics["alerts"]["tp"] + metrics["alerts"]["fn"] > 0
                and metrics["alerts"]["tn"] + metrics["alerts"]["fp"] > 0
                and metrics["age_alerts"]["tp"] + metrics["age_alerts"]["fn"] > 0
                and metrics["age_alerts"]["tn"] + metrics["age_alerts"]["fp"] > 0
            ) if metrics else False,
            "error_count": len(failures), "errors": failures,
            "predictions": samples,
        }
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="MedSafe four-engine held-out evaluation")
    parser.add_argument("manifest", type=Path, help="JSONL with human-confirmed image labels")
    parser.add_argument("--output", type=Path, default=Path("04_results/ocr_independent_benchmark.json"))
    parser.add_argument("--engines", nargs="+", choices=ENGINES, default=list(ENGINES))
    parser.add_argument("--preprocess", choices=MODES, default="none")
    parser.add_argument(
        "--synthetic-development-only", action="store_true",
        help="Use fictional fixture thresholds; generated truth is NOT clinical evidence",
    )
    args = parser.parse_args(argv)
    result = run_benchmark(
        args.manifest, engines=args.engines,
        require_human=not args.synthetic_development_only,
        preprocess=args.preprocess,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(args.output)
    overview = {
        name: {key: result["engines"][name][key] for key in (
            "coverage", "ocr_eligible", "thesis_eligible", "dose_alert_evaluated_n",
            "age_alert_evaluated_n", "timing", "error_count"
        )} for name in result["engines"]
    }
    print(json.dumps({"output": str(args.output), "engines": overview}, indent=2))
    # OCR-only held-out experiments can succeed even when clinical evidence
    # is unavailable, but the file explicitly marks clinical metrics as absent.
    return 0 if all(item["ocr_eligible"] or (
        args.synthetic_development_only and item["error_count"] == 0
    ) for item in result["engines"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
