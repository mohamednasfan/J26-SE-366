# MedSafe-AI project structure

This project keeps application code, the web interface, test files, local data, and model files separate.

```text
medsafe_core/
├── medsafe/                 Application logic and API implementation
├── backend/                 Compatibility entry point for the API server
├── frontend/                Web interface source and production build
├── tests/                   Automated checks
├── 02_models/              Local research model files
├── examples/                Safe sample images and demonstration inputs
├── runtime_data/            Local database, uploads, and generated reports
├── runtime_tools/           Optional local tools such as the OCR installer
├── scripts/                 Maintenance and verification scripts
├── static/                  Legacy static assets kept for compatibility
├── model_cache/             Downloaded detector cache
├── .venv/                   Local Python environment
├── setup_and_verify_models.py
├── start_product.py
├── start_windows.bat
├── requirements*.txt
└── README_START_HERE.md
```

Generated caches and local runtime data are ignored by version control. The local database, uploaded files, and the research checkpoint are intentionally retained on this machine.

The application uses Tesseract for the normal product workflow. The verified local research checkpoint is available for the separate model verification workflow and is never replaced silently by generic weights.
