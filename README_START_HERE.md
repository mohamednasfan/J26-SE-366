> **Current release workflow (October 2026):** This repository now uses the modular React frontend, FastAPI API, optional four-engine OCR, and independent evaluation protocol in [docs/INDEPENDENT_EVALUATION_PROTOCOL.md](docs/INDEPENDENT_EVALUATION_PROTOCOL.md). **The Notebook 44 fine-tuned checkpoint is not bundled**; CRAFT + TrOCR requires that exact mounted checkpoint. Installing packages alone is not proof of model readiness. This app is for localhost research only, never clinical clearance.

## Run the current modular application

Install Python 3.11/3.12, Node.js 20+ with npm, and Tesseract if using its baseline. On Windows, run `start_windows.bat`; on macOS/Linux, run `bash start_linux_mac.sh`. These scripts install the core dependencies, build the current React interface, and start the backend at `http://127.0.0.1:8000`. The frontend build is mandatory so a stale offline page cannot silently replace the current UI.

For the optional neural OCR engines, install `requirements-ocr.txt`. Set `MEDSAFE_TROCR_MODEL_DIR` to the **existing Notebook 44 checkpoint directory** containing `model.safetensors` and tokenizer/processor/config files. The application reports unavailable models explicitly and never substitutes a pretrained public TrOCR for the fine-tuned research model.

The **Research** page also includes an interactive four-engine OCR comparison. Upload a fictional or appropriately authorized single-page prescription; the endpoint `/api/compare` sends the same prepared image to each installed OCR engine, reports unverified transcriptions and elapsed times, and does not retain the comparison image. This is an exploratory preview, not a labeled thesis accuracy evaluation.

---

## Archived setup instructions (historical; may describe the older offline interface)

# MedSafe-AI — Prescription Intelligence Research Platform

**Thesis:** Prescription OCR Accuracy + Overdose Detection + Age Dosage Validation

MedSafe-AI is a locally hosted, modular **FastAPI + React + SQLite** research application. It records prescription images, compares four OCR adapters, supports manual transcription review and revisions, retrieves official drug-label candidates, performs **strictly provenance-gated** overdose/age screening, and provides reproducible research benchmark tools.

**Important:** This is software for thesis research, **not a licensed or clinically validated medication device**. It has no public multi-user authentication, no clinical approval, and must not be Internet-exposed or used to prescribe or dispense. An empty reviewed-rules registry is intentional until qualified reviewers approve actual product-specific dosing limits. Clinical safety is never automatically granted.

## 1. Fast local start

### Windows (recommended)

Install Python 3.11 or 3.12, **Node.js 20+ with npm**, and the Tesseract OS executable. The Tesseract binary must be on PATH or installed under the standard Windows Tesseract location. In a terminal opened inside the repository:

    start_windows.bat

This creates a Python virtual environment, installs the baseline dependencies, **builds the current React UI**, and starts http://127.0.0.1:8000 on localhost.

### Linux/macOS

Install Python 3.11+, Node.js 20+ and Tesseract (for Ubuntu: sudo apt install tesseract-ocr). Run:

    bash start_linux_mac.sh

### Docker (baseline research application)

Install Docker Desktop, then run:

    docker compose up --build

The container binds **127.0.0.1:8000 only** and bundles the current React UI. The base Docker image installs the **Tesseract baseline**. Deep-learning OCR engines need the optional local research dependencies and models described below.

The old static offline UI is retained only as a compatibility fallback; the supported start scripts build and serve the redesigned React application. If Node/npm is unavailable, the local launcher explicitly refuses to show stale assets.

## 2. Frontend and architecture

- React/Vite feature modules: Overview, Upload, Prescription Records, Review Workspace, Research & Benchmarks.
- Shared design system and UI components under frontend/src/{app,components,features,lib,styles}.
- FastAPI entry at backend.app.main:app with backend/app/{api,services,research} modules.
- Legacy medsafe/ package contains extraction, preprocessing, adapters, independent evaluation, rule registry, and storage. Existing API and tests remain compatible.
- SQLite local persistence, timestamped revision hash evidence, atomic source-image storage, paginated history, and JSON report export.
- GitHub Actions runs the full Python test suite and React production build on each pull request.

The backend is intentionally **single-user local only**. Industrial code organization does not mean enterprise cybersecurity certification, HIPAA compliance, or clinical regulatory clearance.

## 3. End-to-end workflow

1. Upload a PNG/JPEG/WEBP or single-page PDF (12 MB request cap; image decoder also enforces its own stricter size and pixel limits).
2. Choose one OCR engine: Tesseract, EasyOCR, PaddleOCR or CRAFT + Notebook 44 fine-tuned TrOCR.
3. Choose image input treatment: original, CLAHE, adaptive binarization, or deskew + CLAHE. The original file is never overwritten.
4. Inspect the original prescription beside OCR text, correct it and explicitly confirm the transcription.
5. Review extracted medicine, dose, frequency, route, patient age/weight and missing/ambiguous fields. A revision generates another local audit event and recalculates the screening report.
6. Consult sourced DailyMed, openFDA and RxNorm search candidates. These do **not** automatically verify product identity or establish dose limits.
7. With an independently qualified-reviewer-approved, exact product/route/indication/population rule, screen for a threshold exceedance and an out-of-range age. Validated mg/mcg/g conversions and optional weight-based mg/kg limits are supported. An undecidable context remains NOT_EVALUATED.
8. Export the research report. Clinical clearance is always false.

## 4. Fine-tuned TrOCR and optional OCR engines

The **actual Notebook 44 fine-tuned checkpoint is not included in GitHub**. It was saved under the original Drive project:

    MedSafe_AI_Project/02_models/trocr_finetuned_official_source_dev_notebook44/943e9bd2b5f1a54d/best_model_DEVELOPMENT_ONLY/

Copy this model folder to a local folder or mount Google Drive. The model must include config.json, model.safetensors and the associated processor/tokenizer files. Configure MEDSAFE_TROCR_MODEL_DIR before starting the app, for example:

    # Linux/macOS
    export MEDSAFE_TROCR_MODEL_DIR="/absolute/path/to/best_model_DEVELOPMENT_ONLY"

    # Windows PowerShell
    $env:MEDSAFE_TROCR_MODEL_DIR="C:\path\to\best_model_DEVELOPMENT_ONLY"

Install optional model dependencies using:

    python -m pip install -r requirements-ocr.txt
    python setup_and_verify_models.py --model-id "/path/to/best_model_DEVELOPMENT_ONLY"

The verification command writes runtime_data/ocr_model_smoke_test.json and attempts real CRAFT detection + Notebook44 inference. The app never silently replaces missing fine-tuned weights with the generic pretrained model.

OCR status reports whether libraries **and** checkpoint files are installed; this is not an independent accuracy certification. The legacy research OCR route uses the same Notebook44 checkpoint.

## 5. Synthetic dataset (300–500 images)

Generate 400 deterministic fictional prescription pages:

    python -m backend.app.research.synthetic --output runtime_data/synthetic --count 400 --seed 20261022

The dataset has train/validation/test splits, transcription and structured fields, fictional overdose and age-label fixtures, blur/illumination/rotation variations, and a JSONL manifest. It is **not** real patient data and is NOT independently human-verified. Never use its dosage thresholds for actual medicines.

For a development-only Tesseract comparison:

    python -m backend.app.research.benchmark runtime_data/synthetic/manifest.jsonl --synthetic-development-only --engines tesseract --preprocess clahe --output runtime_data/ocr_synthetic_development.json

## 6. Four-engine, independently reviewed benchmark

Prepare a test JSONL manifest whose image_path values are relative to the manifest directory. Every record needs:

    {
      "image_id": "TEST-001",
      "image_path": "images/test-001.png",
      "split": "test",
      "human_verified": true,
      "reviewer_id": "independent-reviewer-id",
      "gold_transcript": "Medicine: ...\nDose: ...",
      "gold": {"medicine": "...", "dose": "..."},
      "gold_alert": false,
      "gold_age_flag": false
    }

The final alert labels must be independently adjudicated and based on approved product-specific medical rules; do not invent them. The benchmark requires unique image IDs and image bytes. On exactly the same images/preprocessing, run:

    python -m backend.app.research.benchmark /path/to/human_verified_manifest.jsonl --engines tesseract easyocr paddleocr craft_trocr --preprocess clahe --output runtime_data/ocr_independent_benchmark.json

The output includes per-engine CER, WER, medicine and dose field accuracy, measured latency, and **separately counted** dose/age alert evaluations. Missing clinical rules trigger abstention rather than fabricated safe/unsafe predictions. Machine-readable thesis eligibility additionally requires complete independent evidence, positive and negative examples, and at least 50 verified test images.

Set MEDSAFE_BENCHMARK_RESULTS to that JSON path and restart the application to show aggregate results on the Research page. Individual predictions and patient text are not exposed by the public research metrics endpoint.

The archived 780-image, four-engine word-image comparison remains available in research/historical_baseline_780.json and on the dashboard; it must not be confused with the later fine-tuned Notebook44 model or full-prescription results.

## 7. Dosing rules and provenance

reviewed_rules_EMPTY.json intentionally contains []. Set MEDSAFE_REVIEWED_RULES to another carefully reviewed registry only when an authorized qualified reviewer has verified exact formulation/product, route, indication, population, dose unit, limits, valid source URL/section, date and version. Age bands and mg/kg thresholds can also be included where explicitly supported. This is a **screening rule**, never a diagnosis, dose recommendation or clinical sign-off.

The software cannot independently confirm reviewer professional qualifications, label applicability, local guidelines, product equivalence or patient-specific contraindications. Unverified records must not be labeled approved.

## 8. Verification

    python -m pip install -r requirements-product.txt
    python -m pip install -U pytest
    python -m pytest -q

    cd frontend
    npm install
    npm run build

Inspect the GitHub Actions checks on the latest branch for actual suite and build outcomes. Tests with synthetic fixtures or mocked OCR engines prove software behavior, not clinical accuracy. Real four-model inference, independent gold labels, qualified clinical rule adjudication and the thesis acceptance measurements require their respective datasets and model hardware.

## Privacy and security

- Run only on a trusted, access-controlled local machine or loopback Docker binding.
- Never expose unauthenticated endpoints through public tunnels.
- Store real patient images only with authorization and an appropriate retention/consent policy.
- Uploaded images and corrected transcriptions are stored in local SQLite/files and **not encrypted at rest** by this app.
- Audit timestamps and SHA-256 digests give revision evidence, **not tamper-proof or legally signed audit logs**.
- Use fictional data during demonstrations unless approvals and privacy safeguards are in place.

For source layout, see docs/PROJECT_STRUCTURE.md. For historical OCR evidence, see docs/ARCHIVED_OCR_BASELINE.md.
