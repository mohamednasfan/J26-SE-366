# MedSafe-AI — modular industrial-style research platform

```text
medsafe-ai-prescription-intelligence/
├── backend/app/
│   ├── api/routes/research_results.py    # privacy-limited benchmark endpoints
│   ├── api/routes/prescriptions.py        # legacy route compatibility
│   ├── core/config.py                    # runtime configuration
│   ├── research/benchmark.py             # held-out 4-engine OCR experiment
│   ├── research/synthetic.py             # reproducible 300–500-image generator
│   ├── services/review_service.py        # age/dose/weight/label warning orchestration
│   ├── services/{ocr,safety}_service.py  # model and analysis facades
│   └── main.py                           # ASGI entry point
├── medsafe/
│   ├── api_product.py                    # established API routes and upload workflow
│   ├── ocr_product.py                    # Tesseract, EasyOCR, PaddleOCR, CRAFT+TrOCR
│   ├── trocr.py                          # Notebook44 fine-tuned research checkpoint
│   ├── extraction.py / pipeline.py       # typed field extraction and orchestration
│   ├── rule_registry.py / validation.py  # source-gated screening and safety checks
│   ├── references.py                     # DailyMed/openFDA/RxNorm evidence retrieval
│   ├── storage.py                        # local SQLite data and uploads
│   └── evaluation.py                     # CER/WER, fields, alerts, age and timing
├── frontend/src/
│   ├── app/App.jsx                       # product shell
│   ├── components/                       # reusable navigation, alerts, cards
│   ├── features/                         # Overview, Upload, Library, Review, Research
│   ├── lib/api.js                        # shared HTTP client
│   └── styles/app.css                    # responsive product design system
├── research/historical_baseline_780.json # aligned archival four-model evidence
├── docs/                                 # experiment and deployment documentation
├── tests/                                # Python unit + integration tests
├── .github/workflows/                    # Python suite + frontend build CI
├── Dockerfile / compose.yaml             # loopback-only local container deployment
├── examples/                              # fictional test inputs
└── reviewed_rules_EMPTY.json             # no unapproved clinical thresholds
```

## Compatibility policy

The established FastAPI API continues to live in `medsafe.api_product` while clinical screening is independently organized in `backend/app/services/review_service.py` and OCR research is organized under `backend/app/research`. This incremental extraction preserves clients and existing tests. `backend.app.main:app` exposes the same application. React is bundled for deployment while the earlier offline UI remains a fallback.

## Safety boundary

The codebase is organized for professional engineering but is **not a clinically approved device**. It does not provide identity management, encrypted multi-tenant hosting, independently signed clinical evidence, or regulatory certification. The Docker Compose port binds only to host loopback; patient data must never be sent to unsecured public deployments.

The separate model files, patient data, caches and generated synthetic images are excluded from source control. Rule files remain empty for real medication until a qualified reviewer verifies each formulation, dose limit, age context and source section.
