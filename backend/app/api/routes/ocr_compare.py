"""On-demand identical-image OCR comparison for controlled research.

This is a comparison *preview*: no ground-truth labels, safety decisions,
or clinical validation are implied. Input is not persisted in the comparison
endpoint and all engines receive the same prepared image bytes.
"""
from __future__ import annotations

import hashlib
import time

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from medsafe.evaluation import edit_distance, norm
from medsafe.extraction import extract_prescription
from medsafe.ocr_product import OCRUnavailable, recognize
from medsafe.preprocessing import MODES, prepare_ocr_bytes

router=APIRouter(prefix="/api/compare",tags=["research"])
ENGINES=("tesseract","easyocr","paddleocr","craft_trocr")
ALLOWED_EXT={".png",".jpg",".jpeg",".webp",".pdf"}
MAX_COMPARE_IMAGE_BYTES=8*1024*1024
MAX_REFERENCE_LENGTH=12000
PREVIEW_FIELDS=('medicine','dose','frequency','age','route','strength')
CORE_FIELDS=('medicine','dose','frequency','age','route')



def preview_extraction(text: str) -> dict:
    """Extract OCR field proposals only; strength is never an administered dose."""
    blocks=extract_prescription(text[:MAX_REFERENCE_LENGTH],allow_unlabeled=True)
    medications=[]
    for i,block in enumerate(blocks,1):
        raw=block.get('fields') or {}
        fields={key:str(raw.get(key) or '').strip() for key in PREVIEW_FIELDS}
        medications.append({
            'index':i,'fields':fields,
            'candidate_only':bool(block.get('candidate_only')),
            'missing_fields':[key for key in CORE_FIELDS if not fields[key]],
            'status':'OCR_CANDIDATE_UNVERIFIED' if block.get('candidate_only') else 'OCR_FIELDS_UNVERIFIED',
            'source_line':block.get('raw_source_line')
        })
    detected=sum(bool(m['fields'][k]) for m in medications for k in CORE_FIELDS)
    total=len(medications)*len(CORE_FIELDS)
    return {'medications':medications,'medication_count':len(medications),
            'field_coverage':{'detected':detected,'possible':total,
                              'ratio':round(detected/total,4) if total else None,
                              'description':'Fields detected, not verified correct'},
            'clinical_clearance':False}


def reference_metrics(text: str, reference: str):
    """Illustrative single-image errors; user input is not independent ground truth."""
    if not reference.strip():
        return None
    gold,pred=norm(reference),norm(text)
    words,recognized=gold.split(),pred.split()
    return {'cer':round(edit_distance(gold,pred)/len(gold),6) if gold else None,
            'wer':round(edit_distance(words,recognized)/len(words),6) if words else None,
            'reference_chars':len(gold),'reference_words':len(words),
            'reference_origin':'USER_ENTERED_NOT_INDEPENDENTLY_VERIFIED',
            'valid_thesis_accuracy_result':False}

@router.post("")
async def compare_ocr(
    file: UploadFile=File(...),
    preprocess: str=Query("none",pattern="^(none|clahe|adaptive|deskew_clahe)$"),
    reference_text: str=Form(""),
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
    if len(reference_text)>MAX_REFERENCE_LENGTH:
        raise HTTPException(422,"Reference transcription exceeds 12,000 characters.")
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
                "extraction":preview_extraction(str(result.get("text") or "")),
                "reference_metrics":reference_metrics(str(result.get("text") or ""),reference_text),
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
        "schema":"medsafe.ocr_comparison.v2",
        "image_sha256":digest,
        "preprocessing":processing,
        "engines":outputs,
        "completed_engines":sum(x["status"]=="COMPLETED" for x in outputs.values()),
        "n_engines":len(ENGINES),
        "source_retained":False,
        "reference_used":bool(reference_text.strip()),
        "reference_independently_verified":False,
        "has_independent_ground_truth":False,
        "valid_thesis_accuracy_result":False,
        "clinical_clearance":False,
        "note":"Field detection is not field accuracy. Reference CER/WER, if provided, comes from user-entered text, not independent thesis evaluation."
    }
