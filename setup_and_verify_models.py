"""Verify the MedSafe-AI research checkpoint and real inference."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEFAULT_MODEL=str(ROOT / "02_models" / "trocr_finetuned_experimental_notebook35" / "best_model_EXPERIMENTAL")

def run(cmd):
    print("+", " ".join(map(str,cmd)), flush=True)
    subprocess.run(cmd,cwd=ROOT,check=True)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install",action="store_true",help="Install app and OCR requirements")
    ap.add_argument("--download-only",action="store_true",help="Load and cache both models without image inference")
    ap.add_argument("--image",type=Path,default=ROOT/"examples"/"synthetic_prescription.png")
    ap.add_argument("--output",type=Path,default=ROOT/"runtime_data"/"ocr_model_smoke_test.json")
    ap.add_argument("--model-id",default=DEFAULT_MODEL,help="Local verified MedSafe-AI research checkpoint directory")
    args=ap.parse_args(argv)
    os.environ["MEDSAFE_RESEARCH_TROCR"]=args.model_id
    os.environ.setdefault("HF_HOME",str(ROOT/"model_cache"/"huggingface"))
    os.environ.setdefault("EASYOCR_MODULE_PATH",str(ROOT/"model_cache"/"easyocr"))
    Path(os.environ["HF_HOME"]).mkdir(parents=True,exist_ok=True)
    Path(os.environ["EASYOCR_MODULE_PATH"]).mkdir(parents=True,exist_ok=True)
    report={"status":"FAILED","model":args.model_id,"detector":"EasyOCR CRAFT",
            "python":sys.version.split()[0],"platform":platform.platform(),
            "image":str(args.image),"steps":{},"cache_paths":{"hf":os.environ["HF_HOME"],
            "easyocr":os.environ["EASYOCR_MODULE_PATH"]}}
    start=time.monotonic()
    try:
        if args.install:
            run([sys.executable,"-m","pip","install","-r","requirements-ocr.txt"])
            report["steps"]["dependencies_installed"]=True
        for name in ("torch","transformers","easyocr"):
            if importlib.util.find_spec(name) is None:
                raise RuntimeError(f"Missing dependency '{name}'. Re-run with --install.")
        from medsafe.ocr_product import _craft, _recognizer, recognize
        print("[1/3] Downloading/loading CRAFT detector...",flush=True)
        _craft()
        report["steps"]["craft_loaded"]=True
        print("[2/3] Loading the MedSafe-AI research checkpoint...",flush=True)
        _recognizer()
        report["steps"]["trocr_loaded"]=True
        if not args.download_only:
            print("[3/3] Running real OCR on test image...",flush=True)
            if not args.image.is_file():
                raise FileNotFoundError(f"Sample image missing: {args.image}")
            result=recognize(args.image.read_bytes(),engine="craft_trocr")
            report["steps"]["inference_completed"]=True
            report["regions"]=len(result["regions"])
            report["nonempty_predictions"]=sum(bool(r["text"].strip()) for r in result["regions"])
            report["warnings"]=result["warnings"]
            report["transcription_preview"]=result["text"][:800]
            if report["regions"]<1 or report["nonempty_predictions"]<1:
                raise RuntimeError("OCR produced no readable regions; setup is not verified.")
        report["status"]="PASSED"
        print("PASS: Model initialization"+(" and image inference" if not args.download_only else ""),flush=True)
    except Exception as exc:
        report["error"]=f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        report["seconds"]=round(time.monotonic()-start,2)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("Verification report:",args.output,flush=True)
    return 0 if report["status"]=="PASSED" else 1

if __name__=="__main__":
    raise SystemExit(main())
