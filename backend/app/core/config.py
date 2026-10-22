"""Environment-backed configuration for the local research deployment."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("MEDSAFE_DATA_DIR", ROOT / "runtime_data"))
MODEL_CACHE = Path(os.getenv("HF_HOME", ROOT / "model_cache" / "huggingface"))
EASYOCR_CACHE = Path(os.getenv("EASYOCR_MODULE_PATH", ROOT / "model_cache" / "easyocr"))
TROCR_MODEL_ID = os.getenv("MEDSAFE_PRETRAINED_TROCR", "microsoft/trocr-base-handwritten")
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
LOCAL_ONLY = os.getenv("MEDSAFE_LOCAL_ONLY", "1") == "1"
