"""On-demand identical-image OCR comparison for controlled research.

This is a comparison *preview*: no ground-truth labels, safety decisions,
or clinical validation are implied. Input is not persisted in the comparison
endpoint and all engines receive the same prepared image bytes.
"""
from __future__ import annotations

import hashlib
import time

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from medsafe.ocr_product import OCRUnavailable, recognize
from medsafe.preprocessing import MODES, prepare_ocr_bytes

router=APIRouter(prefix="/api/compare",tags=["research"])
ENGINES=("tesseract","easyocr","paddleocr","craft_trocr")
ALLOWED_EXT={".png",".jpg",".jpeg",".webp",".pdf"}
MAX_COMPARE_IMAGE_BYTES=8*1024*1024


@router.post("")
async def compare_ocr(
    file: UploadFile=File(...),
    preprocess: str=Query("none",pattern="^(none|clahe|adaptive|deskew_clahe)$"),
):
    """Return per-engine transcriptions and measured durations, including failures.

    Returned text remains unverified; model absence is never hidden by another
    engine's prediction. Comparison images are never written to SQLite.
    """
    filename=(file.filename or "unknown").replace("\\","/").rsplit("/",1)[-1]
    from pathlib import Path
    suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(415,"Select a PNG, JPEG, WEBP or one-page PDF.")
    raw=await file.read(MAX_COMPARE_IMAGE_BYTES+1)
    if len(raw)>MAX_COMPARE_IMAGE_BYTES:
        raise HTTPException(413,"Maximum comparison file size is 8 MiB.")
    if not raw:
        raise HTTPException(422,"Empty image.")
    # Reuse the same strict decode/raster path as the prescription upload API.
    from medsafe.api_product import _raster
    data,_=_raster(raw,suffix)
    try:
        prepared,processing=prepare_ocr_bytes(data,mode=preprocess)
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(422,"Image preprocessing unavailable: "+str(exc)[:210]) from exc
    digest=hashlib.sha256(data).hexdigest()
    outputs={}
    for engine in ENGINES:
        started=time.perf_counter()
        try:
            result=recognize(prepared,engine=engine)
            outputs[engine]={
                "status":"COMPLETED",
                "text":str(result.get("text") or ""),
                "region_count":len(result.get("regions") or []),
                "elapsed_seconds":round(time.perf_counter()-started,5),
                "warnings":result.get("warnings") or [],
                "clinical_clearance":False,
            }
        except (OCRUnavailable,RuntimeError,ImportError,ValueError) as exc:
            outputs[engine]={
                "status":"UNAVAILABLE",
                "text":None,
                "elapsed_seconds":round(time.perf_counter()-started,5),
                "reason":str(exc)[:280],
                "clinical_clearance":False,
            }
    return {
        "schema":"medsafe.ocr_comparison.v1",
        "image_sha256":digest,
        "preprocessing":processing,
        "engines":outputs,
        "completed_engines":sum(x["status"]=="COMPLETED" for x in outputs.values()),
        "n_engines":len(ENGINES),
        "source_retained":False,
        "has_independent_ground_truth":False,
        "valid_thesis_accuracy_result":False,
        "clinical_clearance":False,
        "note":"Preview only. Text must be reviewed against its original image. No accuracy metric without independent ground truth."
    }
