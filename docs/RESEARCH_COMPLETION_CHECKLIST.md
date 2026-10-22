# MedSafe-AI completion and evidence checklist

Status: research prototype. This document does not certify clinical safety or thesis target achievement.

## Implemented on this branch
- Hardened reviewed-rule registry against nonfinite/boolean thresholds, invalid age intervals, future review dates, duplicate context rules, and incomplete matching context.
- Added synthetic-only regression tests for the fail-closed reviewed-rule policy.
- Existing application retains human transcription confirmation, no auto-dispense, and no clinical clearance.

## Still requiring independently sourced evidence
1. A qualified reviewer must approve product-specific drug rules with formulation, indication, route, age/weight context, dated source section, and version. Do not populate the registry by copying unreviewed search snippets.
2. Four OCR engines (Tesseract, EasyOCR, PaddleOCR, TrOCR) must be run on the same held-out prescription images with human-verified transcripts and CER/WER plus medicine/dose field accuracy. Do not report results from an unfilled template.
3. Verify the actual TrOCR model checkpoint in the runtime environment; large local checkpoints are intentionally not in GitHub.
4. Generate and independently label the planned 300–500 synthetic prescription images; isolate held-out data and record generation seed, image IDs, degradations, and ground truth.
5. Independently adjudicate overdose and age-validation alerts, including negative and indeterminate cases, before computing precision, recall, and accuracy.
6. Measure end-to-end processing time per image in the target environment.
7. Run the entire backend test suite and frontend build after merging. Synthetic regression tests are not clinical validation.

## Safe interpretation
- BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY does not mean a prescription is safe.
- NOT_EVALUATED or UNABLE_TO_VALIDATE must remain unresolved and require professional review.
- A source label excerpt is not an approved dose threshold.
- No clinical clearance, autonomous prescribing, or dispensing is supported.

## Local verification
```bash
python -m pytest -q
cd frontend && npm install && npm run build
```
