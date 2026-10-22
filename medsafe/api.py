"""FastAPI prescription-to-validation proof-of-function, with trained TrOCR integration."""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Any
from .pipeline import analyze_text, analyze_image
from .trocr import checkpoint_status, ModelNotReady

app=FastAPI(title='MedSafe-AI Core Application',version='0.4.0',
    description='Research prototype with existing fine-tuned TrOCR; not clinical advice.')

class TextRequest(BaseModel):
    text: str=Field(min_length=1,max_length=12000)
    references: bool=False

@app.get('/',response_class=HTMLResponse)
def home():
    return (Path(__file__).parent.parent/'static'/'index.html').read_text(encoding='utf-8')

@app.get('/api/models')
def models():
    status=checkpoint_status()
    return {'trocr_notebook44':status,'tesseract':{'installed':_has_tesseract()},
            'model_validation':'DEVELOPMENT_ONLY_NOT_CLINICALLY_VERIFIED',
            'active_engine_auto':'trocr' if status['ready_for_load'] else 'tesseract'}

def _has_tesseract():
    import shutil
    return shutil.which('tesseract') is not None

@app.get('/api/health')
def health():
    model=checkpoint_status()
    return {'status':'ok','model_trained':model['ready_for_load'],
            'model_checkpoint_detected':model['ready_for_load'],
            'model_verified_by_live_inference':False,
            'active_ocr_engine':'trocr' if model['ready_for_load'] else 'tesseract',
            'clinical_use_permitted':False,'research_only':True}

@app.post('/api/analyze-text')
def text_api(payload:TextRequest):
    try:return analyze_text(payload.text,with_references=payload.references)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.post('/api/analyze-image')
async def image_api(request:Request,references:bool=False,
                    engine:str=Query(default='auto',pattern='^(auto|trocr|tesseract)$')):
    ctype=request.headers.get('content-type','').split(';')[0].strip().lower()
    if ctype not in ('image/png','image/jpeg','image/webp'):
        raise HTTPException(415,'Use a JPEG, PNG or WEBP image.')
    chunks=[];total=0
    async for chunk in request.stream():
        total+=len(chunk)
        if total>8*1024*1024:raise HTTPException(413,'Maximum image size is 8 MiB.')
        chunks.append(chunk)
    try:
        return analyze_image(b''.join(chunks),engine=engine,with_references=references)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except (ModelNotReady,RuntimeError) as exc:raise HTTPException(503,str(exc)) from exc


class ReviewHandoff(BaseModel):
    schema_name: str = Field(alias='schema')
    source_split: str = 'DEVELOPMENT_ONLY'
    transcription_for_review: str = Field(max_length=12000)
    regions: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    clinical_clearance: bool = False
    can_auto_dispense: bool = False

@app.post('/api/review/import')
def import_review(payload: ReviewHandoff):
    if payload.schema_name != 'medsafe.review_only_ocr.v1':
        raise HTTPException(422,'Unsupported review handoff schema')
    if payload.clinical_clearance or payload.can_auto_dispense:
        raise HTTPException(422,'Unsafe clearance flags are prohibited')
    return {'status':'HUMAN_REVIEW_REQUIRED','transcription_for_review':payload.transcription_for_review,
            'regions':payload.regions,'source_split':payload.source_split,
            'clinical_clearance':False,'can_auto_dispense':False,
            'requires_professional_review':True}

class ReviewSubmission(BaseModel):
    corrected_transcription: str = Field(min_length=1,max_length=12000)
    reviewer_confirmed: bool = False

@app.post('/api/review/submit')
def submit_review(payload: ReviewSubmission):
    if not payload.reviewer_confirmed:
        raise HTTPException(422,'Explicit reviewer confirmation required')
    result=analyze_text(payload.corrected_transcription,with_references=False)
    result['reviewer_confirmed_transcription']=True
    result['clinical_clearance']=False
    result['can_auto_dispense']=False
    result['requires_professional_review']=True
    result['clinical_validation_note']='Real-drug dose limits are not validated in this research prototype.'
    return result

@app.get('/review',response_class=HTMLResponse)
def review_page():
    return (Path(__file__).parent.parent/'static'/'review.html').read_text(encoding='utf-8')
