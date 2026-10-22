"""Run the real model initialization/inference smoke test."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from setup_and_verify_models import main
if __name__ == "__main__":
    raise SystemExit(main())
