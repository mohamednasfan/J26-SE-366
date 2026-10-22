"""Privacy-minimizing research result endpoints; aggregate evidence only."""
from __future__ import annotations
import json
import os
from pathlib import Path
from fastapi import APIRouter

router=APIRouter(prefix='/api/research',tags=['research'])

@router.get('/benchmarks')
def benchmark_results():
    location=os.getenv('MEDSAFE_BENCHMARK_RESULTS','')
    if not location:
        return {'status':'NO_INDEPENDENT_RESULTS','engines':{},
                'note':'Configure MEDSAFE_BENCHMARK_RESULTS with a verified benchmark JSON file.'}
    path=Path(location)
    if not path.is_file():
        return {'status':'NO_INDEPENDENT_RESULTS','engines':{},
                'note':'Configured benchmark JSON was not found.'}
    try:
        document=json.loads(path.read_text(encoding='utf-8'))
        if document.get('schema')!='medsafe.ocr_benchmark.v1':
            raise ValueError('Unexpected benchmark schema')
        results={}
        for name,entry in document.get('engines',{}).items():
            if name not in ('tesseract','easyocr','paddleocr','craft_trocr'):
                continue
            results[name]={
                'n_total':entry.get('n_total'), 'n_succeeded':entry.get('n_succeeded'),
                'coverage':entry.get('coverage'),
                'ocr_eligible':entry.get('ocr_eligible') is True,
                'thesis_eligible':entry.get('thesis_eligible') is True,
                'dose_alert_evaluated_n':entry.get('dose_alert_evaluated_n',0),
                'age_alert_evaluated_n':entry.get('age_alert_evaluated_n',0),
                # Aggregate-only metrics remain visible for synthetic development,
                # but the caller must distinguish label_policy and evidence gates.
                'metrics':entry.get('metrics'),
                'timing':entry.get('timing'),
                'error_count':entry.get('error_count',0)
            }
        independently_labeled=document.get('label_policy')=='HUMAN_VERIFIED_TEST_ONLY'
        full_ocr=bool(results) and all(entry['ocr_eligible'] for entry in results.values())
        status='HUMAN_VERIFIED_TEST' if independently_labeled and full_ocr else (
            'INCOMPLETE_TEST' if independently_labeled else 'DEVELOPMENT_ONLY')
        return {'status':status,'engines':results,
                'preprocessing_mode':document.get('preprocessing_mode','none'),
                'dataset_size':document.get('dataset_size'),'generated_utc':document.get('generated_utc'),
                'note':'Individual images, transcripts, filenames and predictions are intentionally not exposed.'}
    except (OSError,ValueError,TypeError,KeyError):
        return {'status':'INVALID_BENCHMARK_FILE','engines':{},
                'note':'Could not read a valid benchmark file.'}

@router.get('/synthetic')
def synthetic_dataset():
    location=os.getenv('MEDSAFE_SYNTHETIC_METADATA','')
    if not location or not Path(location).is_file():
        return {'status':'NOT_CONFIGURED','count':0}
    try:
        data=json.loads(Path(location).read_text(encoding='utf-8'))
        return {'status':'GENERATED' if data.get('schema')=='medsafe.synthetic_dataset.v1' else 'INVALID',
                'count':data.get('count',0),'splits':data.get('splits',{}),
                'human_verified':False,'clinical_evidence':False}
    except (OSError,TypeError,ValueError):
        return {'status':'INVALID','count':0}

@router.get('/historical')
def historical_baseline():
    """Bundled, previously recorded *word-level* results; never thesis release evidence."""
    path=Path(__file__).resolve().parents[4]/'research'/'historical_baseline_780.json'
    try:
        document=json.loads(path.read_text(encoding='utf-8'))
        if document.get('schema')!='medsafe.historical_baseline.v1':
            raise ValueError('Unexpected schema')
        return document
    except (OSError,ValueError):
        return {'status':'NOT_AVAILABLE','n_aligned_images':0,'engines':{}}
