"""Reproducible same-image OCR benchmark. Never invent human ground truth."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from medsafe.evaluation import evaluate, evaluate_readiness
from medsafe.extraction import extract_prescription
from medsafe.ocr_product import recognize, OCRUnavailable

ENGINES = ('tesseract', 'easyocr', 'paddleocr', 'craft_trocr')

def read_manifest(manifest: Path, *, require_human=True):
    root=manifest.resolve().parent
    rows=[]
    for idx, line in enumerate(manifest.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():
            continue
        try: row=json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Manifest line {idx}: invalid JSON') from exc
        if not isinstance(row,dict) or not row.get('image_path') or not row.get('image_id'):
            raise ValueError(f'Manifest line {idx}: image_path and image_id are required')
        path=(root / str(row['image_path'])).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'Manifest line {idx}: image path escapes manifest directory')
        if not path.is_file():
            raise ValueError(f'Manifest line {idx}: image not found: {path}')
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):
            raise ValueError(f'Manifest line {idx}: unsupported image format')
        if not isinstance(row.get('gold_transcript'),str) or not row['gold_transcript'].strip():
            raise ValueError(f'Manifest line {idx}: nonempty gold_transcript required')
        if not isinstance(row.get('gold'),dict):
            raise ValueError(f'Manifest line {idx}: gold field dictionary required')
        rows.append(dict(row,_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if not rows: raise ValueError('No labeled image rows in manifest')
    if require_human:
        readiness=evaluate_readiness(rows)
        if not readiness['ready']:
            raise ValueError('Held-out human-verification gate failed: '+'; '.join(readiness['issues'][:12]))
    ids=[r['image_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Manifest contains duplicate image IDs')
    return rows

def _timing_stats(seconds):
    if not seconds:return {'n':0,'mean_s':None,'median_s':None,'p95_s':None,'max_s':None}
    ordered=sorted(seconds)
    return {'n':len(seconds),'mean_s':round(statistics.mean(seconds),4),
            'median_s':round(statistics.median(seconds),4),
            'p95_s':round(ordered[max(0,int(.95*len(ordered)+.9999)-1)],4),
            'max_s':round(ordered[-1],4)}

def run_benchmark(manifest, *, engines=ENGINES, require_human=True):
    path=Path(manifest)
    rows=read_manifest(path,require_human=require_human)
    chosen=list(engines)
    if not chosen or len(set(chosen))!=len(chosen) or any(e not in ENGINES for e in chosen):
        raise ValueError('Choose one or more unique supported OCR engines')
    output={'schema':'medsafe.ocr_benchmark.v1','generated_utc':datetime.now(timezone.utc).isoformat(),
            'manifest':str(path.resolve()),'dataset_size':len(rows),
            'label_policy':'HUMAN_VERIFIED_TEST_ONLY' if require_human else 'SYNTHETIC_DEVELOPMENT_ONLY_NOT_THESIS_EVIDENCE',
            'environment':{'python':sys.version.split()[0],'platform':platform.platform()},
            'engines':{}}
    for engine in chosen:
        predictions=[]; samples=[];latencies=[];errors=[]
        for item in rows:
            try:
                start=time.perf_counter()
                recognized=recognize(Path(item['_path']).read_bytes(),engine=engine)
                elapsed=time.perf_counter()-start
                text=str(recognized.get('text') or '')
                blocks=extract_prescription(text,allow_unlabeled=True)
                extracted=blocks[0]['fields'] if blocks else {}
                sample={'image_id':item['image_id'],'sha256':item['sha256'],
                        'engine':engine,'transcription':text,'fields':extracted,
                        'elapsed_seconds':round(elapsed,5),'warnings':recognized.get('warnings',[])}
                samples.append(sample);latencies.append(elapsed)
                rec={'gold':item['gold'],'predicted':extracted,
                     'gold_transcript':item['gold_transcript'],'predicted_transcript':text}
                for key in ('gold_alert','gold_age_flag'):
                    if key in item:
                        # OCR-only comparison never invents a clinical alert; annotations can
                        # be evaluated separately against actual pipeline alert predictions.
                        pass
                predictions.append(rec)
            except (OCRUnavailable,ImportError,RuntimeError,ValueError,FileNotFoundError) as exc:
                errors.append({'image_id':item['image_id'],'type':type(exc).__name__,'message':str(exc)[:260]})
        # A failed recognition is not silently omitted from thesis metrics.
        # Require 100% coverage before reporting the acceptance metrics.
        full_coverage=(len(predictions)==len(rows) and not errors)
        output['engines'][engine]={'n_total':len(rows),'n_succeeded':len(predictions),
            'coverage':round(len(predictions)/len(rows),6),'timing':_timing_stats(latencies),
            'metrics':evaluate(predictions) if full_coverage else None,
            'thesis_eligible':bool(full_coverage and require_human),
            'error_count':len(errors),'errors':errors,'predictions':samples}
    return output

def main(argv=None):
    parser=argparse.ArgumentParser(description='Human-verified same-image 4-engine MedSafe OCR benchmark')
    parser.add_argument('manifest',type=Path,help='JSONL rows relative to their image files')
    parser.add_argument('--output',type=Path,default=Path('04_results/ocr_independent_benchmark.json'))
    parser.add_argument('--engines',nargs='+',choices=ENGINES,default=list(ENGINES))
    parser.add_argument('--synthetic-development-only',action='store_true',help='Allow unlabeled synthetic generated truth; never thesis evidence')
    args=parser.parse_args(argv)
    result=run_benchmark(args.manifest,engines=args.engines,require_human=not args.synthetic_development_only)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temp=args.output.with_suffix(args.output.suffix+'.tmp')
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    temp.replace(args.output)
    summary={engine:{k:v[k] for k in ('coverage','thesis_eligible','timing','error_count')}
             for engine,v in result['engines'].items()}
    print(json.dumps({'output':str(args.output),'engines':summary},indent=2))
    return 0 if all(v['thesis_eligible'] or args.synthetic_development_only and v['error_count']==0 for v in result['engines'].values()) else 2

if __name__=='__main__':raise SystemExit(main())
