# MedSafe-AI automatic model setup

Windows: Double-click `INSTALL_AND_RUN_WINDOWS.bat`. Python 3.10 or 3.11 (64-bit) and internet access are recommended.

Linux/macOS: `bash install_and_run_linux_mac.sh`

Manual: `python setup_and_verify_models.py --install`
Cache models only: `python setup_and_verify_models.py --download-only`

The installer creates `model_cache/`, installs requirements, downloads EasyOCR CRAFT and `microsoft/trocr-base-handwritten`, and runs real inference on `examples/synthetic_prescription.png`. On failure, it does not start the app and writes `runtime_data/ocr_model_smoke_test.json`.

First installation requires network access and several GB of disk space; CPU inference may be slow. Re-running reuses model weights. Weights are not embedded. Research only; no autonomous medical decisions.
