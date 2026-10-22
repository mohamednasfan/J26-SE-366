# MedSafe-AI — application with fine-tuned TrOCR integration (v0.2)

**This is the working application source, not another research notebook or comparison report.**

The application accepts a prescription image or transcription, runs the **previously fine-tuned Notebook 44 TrOCR model when its checkpoint is available**, parses labeled medication fields (including multiple medications), validates invalid/missing/contradictory inputs, and presents drug-identity and label **candidates** from RxNorm, DailyMed and openFDA. The current clinical-rule database is *not approved*; the application therefore never labels a real prescription clinically safe. It is a research-only prototype, not for clinical use or dispensing.

## Fine-tuned model already in your Google Drive

The full model weights are **NOT bundled** in this small app ZIP; they remain here:

`MedSafe_AI_Project/02_models/trocr_finetuned_official_source_dev_notebook44/943e9bd2b5f1a54d/best_model_DEVELOPMENT_ONLY/`

The folder already contains `model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`, `processor_config.json` and `preprocessor_config.json`. The training used 2,492 training and 572 validation samples; the saved research report shows 91.78% validation exact-transcription accuracy, **not** validated medicine/dose correctness. It is not an independent test, a medicine detector, or a clinical approval.

## Running locally or in a trusted environment

Python 3.10+:

```bash
python -m pip install -r requirements-model.txt
# install OS tesseract-ocr executable for the baseline fallback
export MEDSAFE_TROCR_MODEL_DIR="/path/to/your/best_model_DEVELOPMENT_ONLY"
python start_app.py
```

Open `http://127.0.0.1:8000` locally. In Google Colab, after mounting the same project Drive, the existing Notebook 44 checkpoint path is detected automatically; you must install `requirements-model.txt` and run the API in a **trusted, access-controlled environment**. Do **not** publicly expose Colab patient-image endpoints using unauthenticated tunnels.

When no checkpoint is mounted, `auto` explicitly identifies a Tesseract fallback. If `MEDSAFE_TROCR_MODEL_DIR` is set incorrectly, auto mode **fails closed** instead of silently switching models. `GET /api/models` shows model readiness; the actual model is loaded lazily on first image inference.

## Main endpoints

- `GET /api/models` — model checkpoint detection and OCR default.
- `GET /api/health` — research-only service status.
- `POST /api/analyze-image?engine=auto|trocr|tesseract&references=false` — raw JPEG/PNG/WEBP request body, max 8 MiB.
- `POST /api/analyze-text` — JSON `{"text":"Medicine: DEMO-DRUG-A\nDose: 100 mg\nFrequency: twice daily\nAge: 30 years\nRoute: oral", "references":false}`.

The frontend shows OCR-derived fields, unresolved issues, an optional editable transcript (rechecking corrected text does *not* clinically approve it), and a technical JSON response.

## Current implemented validations

- Missing, malformed, nonpositive, excessively large or unsupported dose/unit; strength is not automatically equated with administered dose.
- Missing/invalid medicine format, unknown drug-label identity, missing/ambiguous frequency, missing/invalid age and weight, invalid administration route.
- Duplicate fields, conflicting ages/doses, duplicate drug regimens, separate medication blocks and unverified multi-drug interactions.
- Uncertain OCR. TrOCR has **no clinically calibrated confidence score**, so image predictions cannot unblock automated dose checks.
- Optional RxNorm exact/normalized concept query, DailyMed and openFDA official-label candidates; *no match* is not proof of an invalid drug.
- Tesseract OCR, fine-tuned TrOCR adapter, OpenCV auto-crop proposals, line reconstruction, and in-browser image upload.
- Synthetic dosage/age logic for **fictitious `DEMO-DRUG-A` only**. This fixture must never be used to determine safety for real medicines.

## Current limitations — do not obscure these

1. The **existing 1.34-GB TrOCR checkpoint is referenced and loadable by design**; because this execution environment lacks the Transformers package and checkpoint weights, the full real-weight inference path was **not executed here**. Adapter, crop handling, fallback/error states, API and real Tesseract OCR were exercised by local tests. Final Colab/GPU inference still requires an environment with the model folder and dependencies.
2. OpenCV region proposals and line grouping are not a trained YOLO detector. Their text boundaries and semantics are uncertain. For the development image collection, segmentation succeeded on all 200 images, with between 1 and 159 proposals per image and no silent truncation.
3. This code has no validated real-drug dosing table, age/weight/indication rules, interaction engine or clinical overdose detection. Official drug label candidates cannot be treated as exact product, route, indication or dose verification.
4. Full field-extraction accuracy, independent Testing, supervised clinical review and 90%/85% thesis targets remain unverified. Original training/testing splits, reviewer decisions, and 55 quarantined development records are untouched.
5. The UI and API are **not production hardened**. The server binds to localhost, has no authentication and should never be publicly exposed or used for real patients without privacy, security and clinical governance reviews.

## Test command

```bash
python -m pytest -q
```

## Refactored application layout

The runnable application is exposed through `backend/app/main.py`, while the
existing `medsafe/` package remains the compatibility-preserved domain layer.
Use `scripts/setup_models.py` for repeatable CRAFT + pretrained
`microsoft/trocr-base-handwritten` initialization and `scripts/verify_inference.py`
for the real image smoke test. The frontend remains in `frontend/` and is built
with Vite; production serving is handled by the FastAPI catch-all route after
`npm run build`.

The 30 automated tests cover API responses, baseline image OCR, synthetic dose/age flags, invalid medicine/age/weight/dose/frequency, multi-medication grouping, top-level errors from later medicines, RxNorm stub responses, TrOCR selection adapter/segmentation mocks, and fail-closed model handling.


## Working-model integration update (v0.3 / Notebook 47 V2)

This version **changes application code** and reuses the previously fine-tuned
TrOCR checkpoint from Notebook 44; it does not retrain a model and is not a
clinical product. Install `requirements-model.txt` in the GPU Colab runtime.

* `medsafe/segments.py`: illumination-aware OpenCV crop proposals, bounded
  review tiles for merged rows; marks **all** geometry unverified.
* `medsafe/ocr.py`: captures one unverified prediction per proposed region;
  checks counts (no silent crop truncation), records region-level evidence for
  correction, blocks calibrated-confidence claims.
* `medsafe/extraction.py`: parses *provisional* unlabeled medicine-form lines
  (Tab/Cap/Syrup/Injection) into independent medicine candidates, retaining
  product **strength distinct from administered dose**, explicit age only,
  supported frequency tokens/schedules only. This is not reliable medication
  identity recognition on unseen handwritten prescriptions.
* `medsafe/pipeline.py`: blocks unlabeled OCR candidates from safety approval
  and from drug-identity reference lookup pending confirmation.
* `tests/test_notebook47_working_pipeline.py`: additional extraction/geometry
  regression checks; original app tests remain.

**Execution order**: In Colab mount Drive, ensure the existing
`05_demo/medsafe_core_app/` sources contain these v0.3 files, then run the
**existing** Notebook 47 from top to bottom. Cells under “V2” use your own
Notebook 44 checkpoint, `114.jpg` from the development set, and no test set.
The model inference stage must still be executed on the Colab GPU by the user;
passing code tests here is not proof of prescription recognition accuracy.

Enable `SHOW_UNVERIFIED_TEXT=True` only when reviewing the output in your own
Colab session; patient data could appear in OCR output. Treat all predictions
and proposed bounding boxes as unverified; never use this system to dispense,
change, or confirm real medication dosing.


## v0.4 — Integrated full-prescription metadata and review

The app now extracts **explicitly labeled** hospital, doctor, patient, prescription date/ID, diagnosis and allergy fields with source-line evidence, conflict checks, missing-field lists and OCR-unverified indicators. It does not guess unlabeled names, dates, diagnosis or authenticity. The UI shows these fields and offers client-side JSON export for professional review. Rechecking edited OCR text is available.

This is a **functional research prototype, not a finished clinically safe application**. Medicine OCR remains unreliable on full pages, clinical overdose/age-specific real-medication rules are not validated, and the existing fine-tuned model weights must be mounted separately. Do not deploy publicly or process real patient data without privacy/security safeguards.


## v0.5 — reproducible evaluation and reviewed-rule infrastructure

`python evaluate_dataset.py labeled_predictions.jsonl report.json` computes exact normalized field accuracy, CER, WER, and alert precision/recall on **human-labeled** data. The supplied example is a synthetic format template, **not** evidence of performance. The code never claims thesis targets are met without labeled independent testing.

`medsafe/rule_registry.py` enforces provenance, review status and exact product/route/indication/population matches for externally curated rule entries. `reviewed_rules_EMPTY.json` is intentionally empty: **no real medicine dosing limits are preapproved**. A qualified reviewer must approve product-specific source-backed rules before threshold flags can be interpreted; even matching a threshold cannot prove safety. The registry is not automatically used to clear prescriptions.


## v0.6: evidence gate and independent OCR notebook

- `medsafe.evaluation.evaluate_verified_jsonl` refuses to report thesis acceptance on unreviewed, duplicate, or non-test examples.
- `56_independent_ocr_benchmark.ipynb` is a reproducible **Tesseract baseline** for independently transcribed full prescriptions; EasyOCR, PaddleOCR and TrOCR still require measured runs on the same test set.
- These changes do **not** improve the trained TrOCR weights or demonstrate clinical accuracy.
- Real medication-specific dosing thresholds remain unavailable until reviewed references are entered.
