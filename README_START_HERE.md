# MedSafe-AI — Runnable thesis application v1.0

**MedSafe-AI: Prescription OCR Accuracy + Overdose Detection + Age Dosage Validation**

A locally runnable **research application**, built from the pre-existing MedSafe-AI core code. It consists of a FastAPI backend, a bundled zero-dependency browser interface, optional React/Vite frontend source, persistent local SQLite history, a primary **CRAFT + pretrained TrOCR** OCR adapter, a Tesseract baseline, prescription corrections, official-label candidate lookup, and evidence-gated medication warnings.

> **Read this before using it:** The software is a thesis prototype **not a clinically validated product**. Do not upload real patient data to a publicly exposed instance. It never decides that a medication is safe or authorizes dispensing. Dose-limit and age-suitability checks need approved, exact product-specific rules, which are **not** bundled. Without such rules they explicitly report **UNABLE_TO_VALIDATE**. No accurate CER/WER or clinical performance is asserted. A clinician must verify actual medication and dose decisions.

## Fastest way to launch (Windows)

1. Extract this ZIP to a directory, e.g. `Documents/MedSafe_AI_Final`.
2. Open a terminal **inside the `medsafe_core` folder**.
3. With **Python 3.10–3.12** installed, run:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-product.txt
python start_product.py
```

4. Visit **http://127.0.0.1:8000**. The included browser UI works **without npm or React build**.
5. To enable the recommended AI OCR instead of just the baseline, stop the server and run:

```powershell
python -m pip install -r requirements-ocr.txt
python start_product.py
```

First-time CRAFT and pretrained TrOCR inference downloads model weights from their official model hosts. You need internet access, memory (ideally 16 GB+), and preferably an NVIDIA GPU; CPU inference can be slow. Follow the PyTorch installation guide if you need a specific CUDA wheel.

For the **Tesseract baseline**, also install the Tesseract OS executable and ensure `tesseract` is on your PATH (Windows: install Tesseract; Ubuntu: `sudo apt install tesseract-ocr`).

## Fastest way to launch (macOS / Linux)

```bash
cd medsafe_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-product.txt
python -m pip install -r requirements-ocr.txt  # enable primary AI OCR
python start_product.py
```

Open **http://127.0.0.1:8000**. To use Tesseract, also install its OS executable.

**Tested here:** FastAPI API endpoints; SQLite persistence; uploading a real synthetic PNG through Tesseract; review, report, deletion, invalid input handling; and a mocked CRAFT→TrOCR adapter (59 passing tests). **Not tested here:** downloading the pretrained TrOCR and CRAFT weights or running their full neural inference, because optional libraries/weights are not installed in this environment. The React bundle could not be built here because npm dependency downloads were blocked; the bundled offline interface does not need npm.

## App workflow

1. **Overview:** dashboard of locally stored prescriptions and human-review state.
2. **New prescription:** upload PNG, JPEG, WEBP or a **single-page PDF**. Choose recommended `CRAFT + TrOCR`, or explicit `Tesseract baseline`. No text or coordinates are hardcoded.
3. **OCR review:** inspect the source image and CRAFT detection overlays, edit the entire transcription. OCR output is always unverified.
4. **Structured extraction:** after confirming the text against the image, parse lines labeled `Medicine:`, `Dose:`, `Frequency:`, `Age:`, `Route:`, etc. Unrecognized fields are left blank; do not silently assume product strength equals administered dose.
5. **Evidence-gated safety report:** identify missing, conflicting, invalid, ambiguous or duplicate fields. Return **UNABLE_TO_VALIDATE** without an applicable approved medication limit/age rule.
6. **Optional reference candidates:** the report can query RxNorm, DailyMed and openFDA on request; returned labels do not automatically establish exact drug identity, safe dosing or age appropriateness.
7. **History & export:** SQLite local record storage; review report page, JSON export, browser print, permanent deletion.
8. **Research dashboard:** explains models and accurately lists metrics as *not yet independently established*.

### Recommended reviewed transcript format

For a single medication:

```
Patient: Jane Example
Age: 30 years
Medicine: [independently verified medicine name]
Strength: [product concentration or strength, if known]
Dose: [administered amount, e.g. 100 mg]
Frequency: twice daily
Route: oral
```

For multiple medicines, repeat `Medicine:`, `Strength:`, `Dose:`, `Frequency:`, `Route:` blocks. Age and weight are patient-level fields shared by all explicit medicine blocks.

Optional fields for source-reviewed dosing-rule matches:

```
Product Identifier: [verified product identifier]
Indication: [verified clinical indication]
Population: [verified population]
```

These are not guessed from handwriting or age. They must come from independent confirmation by a qualified reviewer, using appropriate records. A matching dose limit still does **not** prove clinical safety.

## Clinical-reference rule infrastructure

A verified rule registry is **empty by default**, at `reviewed_rules_EMPTY.json`. The `medsafe/rule_registry.py` module checks that a rule has ingredient, exact product identifier, route, indication, population, unit, maximum single and daily limits, public source URL and section, reviewer identity, review date, version and the `APPROVED_BY_QUALIFIED_REVIEWER` status. Optional `min_age_years` and `max_age_years` allow **source-reviewed age-band warnings** (not personalized dose verification). The app does not import raw web snippets as thresholds. A rule match requires exact, independently confirmed context and compatible units and frequency. Set `MEDSAFE_REVIEWED_RULES` to the path of the approved JSON file only after source validation and clinical governance approval.

No dose limits or age rules for real drugs are shipped; this avoids giving a dangerous impression of validated safety.

## Recommended model stack

- **CRAFT detector:** via EasyOCR's detection-only API (`easyocr.Reader(['en'], detector=True, recognizer=False)`). We use model-detected rectangles; no prescription-template coordinates.
- **TrOCR pretrained handwriting model:** `microsoft/trocr-base-handwritten`, loaded via Hugging Face Transformers. No fine-tuned checkpoint required to run the primary pipeline.
- **Baseline:** Tesseract (explicitly selected in the upload form), **not** a silent fallback.
- **Language processing:** conservative labeled-field extraction and unresolved candidate flagging; not a general clinical NLP extractor.
- **Reference candidates:** RxNorm, DailyMed and openFDA through an on-demand, server-to-server call.
- **Backend:** Python / FastAPI / SQLite.
- **Frontend:** responsive offline-ready HTML/CSS/JS interface (immediately served), plus React/Vite source (`frontend/src/`) for future frontend development. If you have npm access, `cd frontend && npm install && npm run build` makes the server automatically prefer the React production build.

### Configuration

| Variable | Purpose |
| --- | --- |
| `MEDSAFE_PRETRAINED_TROCR` | Model ID or local checkpoint directory, default `microsoft/trocr-base-handwritten` |
| `MEDSAFE_OFFLINE=1` | Forces local-only TrOCR weights; raises an explicit error if absent |
| `MEDSAFE_DATA_DIR` | Location of SQLite database and uploaded images; default `runtime_data/` |
| `MEDSAFE_REVIEWED_RULES` | Clinician-reviewed dose-limit and optional age-band rule registry |

API docs at **http://127.0.0.1:8000/docs**. Basic health probe at `/api/health`. Model readiness at `/api/models`.

## Development / verification

```bash
python -m pytest -q
```

The provided test suite includes 59 tests as of the packaged build; run again in your own environment after installing dependencies.

If frontend npm packages are available:

```bash
cd frontend
npm install
npm run build
# python start_product.py then serves React dist automatically
```

Or run `npm run dev` alongside Python for Vite live reload. Its proxy targets the Python server on localhost port 8000.

## Honest limitations and thesis completion checklist

- First-run heavyweight pretrained neural OCR not executed in this build environment; actual model readiness is shown by the app. On-device inference and accuracy require model download, compatible Torch/Transformers/EasyOCR versions and runtime testing.
- CRAFT crops can split or merge prescription lines; TrOCR can misread medicine names and digits. It does not output clinically calibrated token confidence.
- Structured extraction is conservative rule-based parsing, not a validated medicine entity linking model. It will miss unlabeled handwritten fields and leave ambiguous instructions unresolved.
- Real-medication dose thresholds, age-appropriateness, dose per kg, interaction analysis and clinical rules are not automatically populated. **No actual overdose verdict** is issued in the absence of qualified reviewed rules.
- Independent evaluation still requires held-out prescription images with genuinely human-verified reference labels and clinician-reviewed alert outcomes. Do not substitute pretrained OCR output for gold labels.
- No authentication, encryption, network access controls, audit-grade identity verification or clinical regulatory review. It must not be hosted publicly or used for real patient healthcare.
- Multi-page PDFs are rejected; single-page image/PDF only. Uploaded images are kept locally until deleted. Default image decoder has an 8 MiB image limit even though the request body can be 12 MiB to support PDF; very large inputs fail with a readable error.

## Thesis sources

Project alignment is based on the uploaded MedSafe-AI proposal (Prescription OCR Accuracy + Overdose Detection + Age Dosage Validation) and the pre-existing MedSafe-AI Core App v0.7. The project proposal sets out comparing Tesseract, EasyOCR, PaddleOCR and TrOCR and using DailyMed/openFDA information for dose/age reference checks. This runnable application's active OCR is CRAFT+TrOCR with optional Tesseract; other OCR benchmark modules are research follow-up work, not misrepresented as already implemented.

## Model-enabled installation and verification

For a **model-enabled** setup, use `INSTALL_AND_RUN_WINDOWS.bat` on Windows, or `bash install_and_run_linux_mac.sh` on Linux/macOS. These installers install OCR dependencies, download official CRAFT and TrOCR weights on first use, and **refuse to start the server if real model inference fails**. The verification report is saved in `runtime_data/ocr_model_smoke_test.json`. To re-test an uploaded image locally, run `python setup_and_verify_models.py --image path/to/prescription.png`. Model downloads require internet access and adequate RAM/disk; the ZIP intentionally does not embed multi-gigabyte third-party weights. A passing smoke test verifies executable OCR, **not** prescription correctness or clinical safety.
