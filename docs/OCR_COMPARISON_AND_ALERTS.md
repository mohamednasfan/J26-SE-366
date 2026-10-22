# OCR comparison and review alerts — application guide

## Where the features appear

**New analysis → Choose analysis mode** provides a single OCR engine (saved prescription workflow) or a four-engine comparison (ephemeral comparison, **not** a saved prescription). The **Research & benchmarks** page also retains the comparison tool.

All engines receive the identical preprocessed image. The comparison lists each engine's execution result, time in seconds, unverified OCR transcript, geometric region count, and recognized medicine/dose/frequency/age/route/strength fields. Switch model buttons to examine the output. Missing libraries or the Notebook 44 checkpoint are displayed as unavailable; one model never secretly substitutes for another.

The optional **reference transcription** box enables single-image CER/WER against text entered by the operator. The returned reference label is always `USER_ENTERED_NOT_INDEPENDENTLY_VERIFIED`. These are demonstrations, **not** independent thesis measurements and **not** population accuracy; a higher detected-field count does not mean greater clinical correctness.

## Installation for full comparison

The default baseline is Tesseract. To enable the other engines, install the optional dependencies:

```bash
python -m pip install -r requirements-ocr.txt
```

Set `MEDSAFE_TROCR_MODEL_DIR` to the **actual** Notebook 44 fine-tuned checkpoint folder from the authorized Drive location (containing the model, processor, and tokenizer files). The weights are not in GitHub. Verify real inference separately with:

```bash
python setup_and_verify_models.py --model-id "/absolute/path/to/best_model_DEVELOPMENT_ONLY"
```

Restart the local app after installation. Model readiness shown on the UI is environment-specific and must not be mistaken for measured accuracy.

## Alert behavior

The underlying parser and safety-blocking logic are not weakened. After explicit human confirmation of transcription:

- Multiple `MISSING_*` findings for one medication appear as **one actionable transcription review card**. Expand it to see every original warning.
- Conflicts and duplicate instructions have distinct **blocking inconsistency** cards.
- Clinically sourced, genuinely approved dose-threshold and age-range flags receive separate **reviewed-rule warnings**, never an automated overdose diagnosis.
- Diagnostic uncertainty and ancillary advice are available in **Other notes and OCR limitations**.
- Missing or inapplicable reviewed clinical rules remain **Unable to validate**, not safe.

Use **Check or correct transcription** to return to the source-image review. Medication cards show actual available fields, label evidence links where supported, and reasons why screening could not proceed.

## Limits and quality assurance

All OCR output may be wrong. A recognized product strength is not automatically an administered dose. Tesseract may perform poorly on handwriting, and missing medicines cannot be reconstructed without a human. This research-only app has no clinical clearance, public authentication, or approved real-drug rules by default.

Tests:

```bash
python -m pytest -q tests/test_ocr_comparison_review_ux.py
cd frontend && npm run test:unit && npm run build
```

For valid thesis CER/WER and alert precision/recall, follow `docs/INDEPENDENT_EVALUATION_PROTOCOL.md` with independently annotated held-out prescriptions and qualified clinical reviewers, **not** the interactive one-image comparison.
