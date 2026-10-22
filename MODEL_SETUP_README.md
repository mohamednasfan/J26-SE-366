# MedSafe-AI Model Setup — TrOCR Notebook 44

The clinical-review application and the four-engine research adapter now use the **same fine-tuned TrOCR model from Notebook 44**. Earlier Notebook 35 or generic Microsoft pretrained weights are **not** used as an automatic fallback.

## Install
- Windows: run `INSTALL_AND_RUN_WINDOWS.bat` after preparing the checkpoint.
- Linux/macOS: run `bash install_and_run_linux_mac.sh`.
- Manual: `python -m pip install -r requirements-ocr.txt`.

## Provide the model weights
1. Copy the trained **Notebook 44** model folder from the original Google Drive project to `02_models/trocr_notebook44/best_model_DEVELOPMENT_ONLY`, or another local path.
2. Set `MEDSAFE_TROCR_MODEL_DIR` to that directory (Windows PowerShell: `$env:MEDSAFE_TROCR_MODEL_DIR='C:\\path\\to\\model'`; Linux: `export MEDSAFE_TROCR_MODEL_DIR='/path/to/model'`).
3. Run `python setup_and_verify_models.py --model-id "<path>"` to check CRAFT + TrOCR initialization and actual image inference.
4. Review `runtime_data/ocr_model_smoke_test.json` for evidence of model-load and inference success.

The checkpoint is not stored in the source repository. A package import, a directory name, or a development-validation score never proves the checkpoint is loaded correctly or that its accuracy targets have been achieved on an independent test set.

A missing checkpoint triggers an explicit error. Select Tesseract/EasyOCR/PaddleOCR separately if required; the chosen TrOCR engine never silently switches weights.
