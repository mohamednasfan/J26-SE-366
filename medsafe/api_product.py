"""MedSafe-AI thesis web application API. Local research deployment only."""
from __future__ import annotations
import base64,io,json,re,os,time
from pathlib import Path
from typing import Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, HTMLResponse
from pydantic import BaseModel,Field
from PIL import Image
from . import storage
from .ocr_product import recognize,status as ocr_status,OCRUnavailable
from .pipeline import analyze_text
from .rule_registry import load_reviewed_rules, match_rule, assess_reviewed_rule, RuleRegistryError
from .extraction import number_and_unit,parse_frequency
from .references import lookup
from .preprocessing import prepare_ocr_bytes, MODES

app=FastAPI(title='MedSafe-AI | Prescription Intelligence', version='1.0.0',
            description='Research prototype. All OCR is unverified. No clinical approval or automated dispensing.')
# The built React frontend is served from the same origin; localhost dev-only CORS.
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
                   allow_methods=['GET','POST','DELETE'],allow_headers=['Content-Type'])
MAX_SIZE=12*1024*1024
ALLOWED={'.png','.jpg','.jpeg','.webp','.pdf'}

def _raster(file:bytes,suffix:str)->tuple[bytes,str]:
    if suffix=='.pdf':
        try:
            import fitz
            doc=fitz.open(stream=file,filetype='pdf')
            if doc.page_count!=1:raise HTTPException(422,'Please upload a single-page prescription PDF.')
            page=doc[0];pix=page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
            if pix.width*pix.height>15_000_000:raise HTTPException(422,'PDF page too large for OCR')
            return pix.tobytes('png'),'.png'
        except HTTPException:raise
        except Exception as e:raise HTTPException(422,'Invalid PDF or PDF renderer unavailable') from e
    try:
        from .ocr import decode_image
        decode_image(file)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    return file,suffix

@app.get('/api/health')
def health():return {'status':'operational','mode':'LOCAL_RESEARCH_ONLY','clinical_clearance':False}

@app.get('/api/models')
def models():return ocr_status()

@app.get('/api/stats')
def stats():
    items=storage.rows()
    return {'total':len(items),'reviewed':sum(bool(r['reviewer_confirmed']) for r in items),
            'pending':sum(not r['reviewer_confirmed'] for r in items),
            'research_status':'No validated independent OCR accuracy or approved drug-dose rule collection installed'}

@app.post('/api/prescriptions')
async def upload(file:UploadFile=File(...),
                 engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$'),
                 preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)$')):
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    # Preserve the source bytes for review; apply enhancement to OCR input only.
    try:
        ocr_input,prep=prepare_ocr_bytes(data,mode=preprocess)
    except (RuntimeError,ValueError) as exc:
        raise HTTPException(422,'Image preprocessing unavailable or invalid: '+str(exc)[:250]) from exc
    try:ocr=recognize(ocr_input,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['preprocessing']=prep
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),
                       engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$'),
                       preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine,preprocess))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
),
                 preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
)):
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
),
                       preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
),
                 preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
)):
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
)):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
),
                 preprocess:str=Query('none',pattern='^(none|clahe|adaptive|deskew_clahe)
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
)):
    started=time.perf_counter()
    name=(file.filename or 'prescription').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED:raise HTTPException(415,'Upload PNG, JPG, WEBP or single-page PDF')
    content=await file.read(MAX_SIZE+1)
    if len(content)>MAX_SIZE:raise HTTPException(413,'Maximum upload size: 12 MB')
    data,ext=_raster(content,suffix)
    try:ocr=recognize(data,engine=engine)
    except (OCRUnavailable,RuntimeError) as e:raise HTTPException(503,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
    ocr['processing_seconds']=round(time.perf_counter()-started,4)
    pid=storage.create(name,ext,engine,ocr)
    (storage.DATA/(pid+ext)).write_bytes(data)
    return {'id':pid,'filename':name,'status':'REVIEW_REQUIRED','ocr':ocr,
            'image_url':f'/api/prescriptions/{pid}/image','processing_seconds':ocr['processing_seconds'],
            'clinical_clearance':False,'can_auto_dispense':False}

@app.post('/api/prescriptions/batch')
async def upload_batch(files:list[UploadFile]=File(...),engine:str=Query('tesseract',pattern='^(craft_trocr|easyocr|paddleocr|tesseract)$')):
    """Process a bounded local batch while preserving per-image review state."""
    if not files or len(files)>32:
        raise HTTPException(422,'Batch size must be between 1 and 32 files.')
    results=[]
    for file in files:
        try:
            results.append(await upload(file,engine))
        except HTTPException as exc:
            results.append({'filename':file.filename or 'prescription','status':'FAILED','error':exc.detail})
    return {'items':results,'count':len(results),'clinical_clearance':False,'requires_professional_review':True}

@app.get('/api/prescriptions')
def history():return {'items':storage.rows()}

@app.get('/api/prescriptions/{pid}')
def detail(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return {'id':item['id'],'filename':item['filename'],'status':item['status'],
            'created':item['created'],'updated':item['updated'],'engine':item['engine'],
            'original_text':item['original_text'],'corrected_text':item['corrected_text'],
            'reviewer_confirmed':bool(item['reviewer_confirmed']),
            'ocr':json.loads(item['ocr_json']),'report':json.loads(item['report_json']),
            'image_url':f'/api/prescriptions/{pid}/image','clinical_clearance':False,
            'can_auto_dispense':False}

@app.get('/api/prescriptions/{pid}/image')
def image(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    return FileResponse(storage.DATA/item['image_name'],headers={'Cache-Control':'private, no-store'})

class Review(BaseModel):
    corrected_text:str=Field(min_length=1,max_length=12000)
    reviewer_confirmed:bool
    check_references:bool=False


def _rule_assessment(report):
    """Backwards-compatible wrapper around the dedicated review service."""
    from backend.app.services.review_service import assess_report
    return assess_report(report)


@app.post('/api/prescriptions/{pid}/review')
def review(pid:str,payload:Review):
    if not storage.get(pid):raise HTTPException(404,'Prescription not found')
    if not payload.reviewer_confirmed:raise HTTPException(422,'Explicit transcription confirmation required')
    report=analyze_text(payload.corrected_text,ocr_mode=False,with_references=False)
    report=_rule_assessment(report)
    # Do not conflate verified transcription with identity, dosing or clinical signoff.
    report['reviewer_confirmed_transcription']=True
    report['clinical_clearance']=False
    report['can_auto_dispense']=False
    report['requires_professional_review']=True
    report['dose_safety_summary']='UNABLE_TO_VALIDATE' if not any(m['dose_validation_available'] for m in report['medications']) else 'REVIEWED_REFERENCE_THRESHOLD_CHECK_ONLY'
    report['age_safety_summary']='REVIEWED_AGE_RANGE_SCREEN_ONLY' if any(m['reviewed_age_rule']['status']!='UNABLE_TO_VALIDATE' for m in report['medications']) else 'UNABLE_TO_VALIDATE'
    report['disclaimer']='Not medical advice. This tool cannot approve, dispense, or rule out overdose. The corrected transcription and drug-specific guidance must be checked by a qualified clinician.'
    storage.update(pid,payload.corrected_text,report)
    return {'id':pid,'report':report,'status':'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS'}

@app.get('/api/prescriptions/{pid}/report')
def report(pid:str):
    item=storage.get(pid)
    if not item:raise HTTPException(404,'Prescription not found')
    if not item['reviewer_confirmed']:raise HTTPException(409,'Transcription must be explicitly reviewed before reporting')
    return json.loads(item['report_json'])

@app.get('/api/prescriptions/{pid}/audit')
def review_audit(pid:str):
    events=storage.audit(pid)
    if events is None:raise HTTPException(404,'Prescription not found')
    return {'id':pid,'events':events,'retention':'Deleted with prescription record',
            'note':'SHA256 hashes and timestamps record text revisions without duplicating the transcript.'}

@app.delete('/api/prescriptions/{pid}')
def delete(pid:str):
    if not storage.delete(pid):raise HTTPException(404,'Prescription not found')
    return {'deleted':True}

@app.get('/api/reference')
def reference(medicine:str=Query(min_length=2,max_length=80)):
    return lookup(medicine)

@app.get('/api/research')
def research():
    return {'ocr_models':['Tesseract (baseline)','EasyOCR (benchmark adapter)','PaddleOCR (benchmark adapter)','TrOCR (pretrained, primary)'],
            'available_engines':ocr_status().get('benchmark_engines',{}),
            'metric_status':'NO_INDEPENDENT_VERIFIED_TEST_METRICS_IN_APPLICATION',
            'evaluation_policy':'CER/WER and field accuracy require independently verified human references and isolated held-out testing.',
            'targets_not_claimed':{'medicine_name_accuracy':0.90,'dosage_accuracy':0.90,'overdose_precision_recall':0.85,'age_precision_recall':0.85},
            'reference_policy':'DailyMed/openFDA are identity/evidence sources; no dose rule is treated as approved without product, route, indication, population, source, and qualified review.',
            'clinical_clearance':False}

# Versioned research-service router; register before the frontend catch-all.
from backend.app.api.routes.research_results import router as research_results_router
app.include_router(research_results_router)

@app.get('/{path:path}')
def frontend(path:str):
    dist=Path(__file__).parent.parent/'frontend'/'dist'
    if path.startswith('api/') or path=='api':raise HTTPException(404,'API route not found')
    target=(dist/path).resolve()
    if dist.resolve() in target.parents and target.is_file():return FileResponse(target)
    index=dist/'index.html'
    if index.is_file():
        # Keep a small accessible/server-side label in the HTML shell for
        # non-JavaScript health checks and screen readers.
        html=index.read_text(encoding='utf-8')
        if 'PRESCRIPTION INTELLIGENCE' not in html:
            html=html.replace('<div id="root"></div>', '<div id="root"></div><span class="sr-only">PRESCRIPTION INTELLIGENCE</span>')
        return HTMLResponse(html)
    fallback=Path(__file__).parent.parent/'frontend'/'offline'
    fallback_target=(fallback/path.removeprefix('offline/')).resolve() if path.startswith('offline/') else None
    if fallback_target and fallback.resolve() in fallback_target.parents and fallback_target.is_file():return FileResponse(fallback_target)
    return FileResponse(fallback/'index.html')
