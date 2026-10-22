# MedSafe-AI: independent OCR and safety evaluation protocol

## Scope

This protocol evaluates the thesis objectives **Prescription OCR Accuracy + Overdose Detection + Age Dosage Validation** without mixing development and held-out evidence. It does **not** establish that the software is clinically safe or ready for patient care.

### Data partition and labeling

1. Collect independent held-out prescription images with written permission and appropriate de-identification. Never put patient images or transcripts in GitHub.
2. Use a stable `image_id`, one image per row, and `split: "test"`. Do not use an image or a duplicate of it for training, model selection, preprocessing tuning, or thresholds.
3. A human reviewer independently transcribes the **entire** prescription and verifies the medication, administered dose, frequency, age, and route fields. Record a non-identifying `reviewer_id` and set `human_verified: true` only after actual verification.
4. If an image has multiple medications, annotate and evaluate each medication separately in a medication-level dataset. The current `benchmark.py` exact-field metric uses the first parsed block and must **not** be represented as multi-medication accuracy.
5. For overdose and age validation, independently label `gold_alert` and `gold_age_flag` as actual booleans **only** when supported by a qualified reviewer and applicable product/route/indication/weight/age-specific reference. Do not infer these labels from synthetic fixtures or the same rule engine under test.
6. If a label is not supportable, omit it and report the reduced evaluated sample count. **Do not encode unknown as false.**

### Example JSONL manifest

Paths are relative to the manifest file. The following is a schema **example**, not verified data or a usable test sample:

```json
{"image_id":"heldout-0001","image_path":"images/heldout-0001.png","split":"test","human_verified":true,"reviewer_id":"reviewer-pseudonym","gold_transcript":"[manually transcribed prescription text]","gold":{"medicine":"[verified medicine]","dose":"[verified administered dose]","frequency":"[verified schedule]","age":"[verified patient age]","route":"[verified route]"}}
```

The benchmark validates image paths, file hashes, unique IDs, and human verification flags; those checks cannot establish that a label is *truthful*. Audit the human review process separately.

### Run all four OCR engines on the same inputs

From the repository root, install the required Python packages, the OS Tesseract executable, and mount the exact Notebook 44 fine-tuned TrOCR checkpoint:

```bash
python -m pip install -r requirements-product.txt
python -m pip install -r requirements-ocr.txt
export MEDSAFE_TROCR_MODEL_DIR="/absolute/path/to/best_model_DEVELOPMENT_ONLY"
python -m backend.app.research.benchmark data/heldout/manifest.jsonl \
  --engines tesseract easyocr paddleocr craft_trocr \
  --preprocess none \
  --output runtime_data/ocr_independent_benchmark.json
```

For Windows PowerShell use `$env:MEDSAFE_TROCR_MODEL_DIR="C:\\path\\to\\checkpoint"` instead of `export`.

Run separate, explicitly named experiments for `clahe`, `adaptive`, and `deskew_clahe`; do not select the best preprocessing using the held-out test set and then report it as untouched evidence. Preprocessing is applied to the same input image for all four engines in a given run.

To show aggregate results in the app:

```bash
export MEDSAFE_BENCHMARK_RESULTS="$PWD/runtime_data/ocr_independent_benchmark.json"
python start_product.py
```

The full JSON may contain predictions and transcripts. Keep it in a restricted local research folder; the app's `/api/research/benchmarks` endpoint intentionally exposes only aggregate metrics.

### Metrics and reporting

| Measure | Required reporting |
|---|---|
| OCR | Micro-averaged CER, WER, reference character/word counts |
| Field extraction | Exact-match medicine name and administered dose accuracy, denominators and missing predictions |
| Overdose alert | TP, FP, FN, TN, precision, recall, evaluated denominator and abstentions |
| Age suitability | TP, FP, FN, TN, accuracy, evaluated denominator and abstentions |
| Latency | Per-engine mean, median, p95 and maximum measured end-to-end seconds |
| Reliability | OCR errors, unavailable models, model/checkpoint versions, image quality and coverage |

Thesis targets are **CER ≤10%, medicine and dose field accuracy ≥90%, overdose precision and recall ≥85%, age accuracy ≥85%, and ≤10 seconds per image** on the specified cloud GPU. These are research targets, not achieved results. The current acceptance gate also requires at least 50 independent test images, fully paired clinical labels, and minimum positive/negative class support. A statistically justified larger test cohort is preferable.

### Important implementation boundary

- OCR benchmarking is runnable when the actual images, human references, and installed engines are available.
- The clinical-rule registry shipped in the repository is empty. The app deliberately abstains on real-drug dosage and age thresholds until a qualified clinician has approved the exact-context rules.
- Synthetic `SYNTHMED-` cases are for **software development only**. They cannot establish clinical sensitivity, specificity, or patient safety.
- DailyMed and openFDA label text is evidence for professional interpretation, **not** an automatically verified numeric dosing rule.
- The Notebook 44 checkpoint is not included in GitHub. Copy or mount the weights from the project's approved storage; do not replace it with a pretrained public model and call it the fine-tuned result.
- The application is localhost-only and lacks production authentication and patient-data governance. Do not deploy it on the public Internet.
