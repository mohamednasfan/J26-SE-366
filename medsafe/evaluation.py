"""Independent ground-truth field evaluation; never substitute development OCR metrics."""
from __future__ import annotations
import csv
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

FIELDS=('medicine','dose','frequency','age','route','weight','strength')
def norm(s): return re.sub(r'\s+',' ',str(s or '').strip()).casefold()
def edit_distance(a,b):
    p=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        c=[i]+[0]*len(b)
        for j,y in enumerate(b,1): c[j]=min(c[j-1]+1,p[j]+1,p[j-1]+(x!=y))
        p=c
    return p[-1]
def evaluate(records):
    """Records: [{gold:{...},predicted:{...},gold_alert:bool,predicted_alert:bool}]."""
    rows=list(records)
    if not rows: raise ValueError('Evaluation requires labeled records')
    counts={f:{'correct':0,'total':0,'missing':0} for f in FIELDS}
    chars=errors=words=word_errors=0
    tp=fp=fn=tn=0
    for row in rows:
        gold=row['gold']; pred=row['predicted']
        for f in FIELDS:
            g=norm(gold.get(f)); p=norm(pred.get(f))
            if g:
                counts[f]['total']+=1
                counts[f]['correct']+=int(g==p)
                counts[f]['missing']+=int(not p)
        if 'gold_transcript' in row and 'predicted_transcript' in row:
            a=norm(row['gold_transcript']);b=norm(row['predicted_transcript'])
            chars+=len(a);errors+=edit_distance(a,b)
            aw=a.split();bw=b.split();words+=len(aw);word_errors+=edit_distance(aw,bw)
        if 'gold_alert' in row and 'predicted_alert' in row:
            g=row['gold_alert'];p=row['predicted_alert']
            if type(g) is not bool or type(p) is not bool: raise ValueError('Alerts must be labeled booleans')
            tp+=int(g and p);fp+=int(not g and p);fn+=int(g and not p);tn+=int(not g and not p)
    age_metrics=classification_metrics(rows,'gold_age_flag','predicted_age_flag')
    elapsed_metrics=latency_metrics(rows)
    return {'age_alerts':age_metrics,'timing':elapsed_metrics,'n':len(rows),'fields':{f:{**c,'accuracy':c['correct']/c['total'] if c['total'] else None} for f,c in counts.items()},
            'ocr':{'CER':errors/chars if chars else None,'WER':word_errors/words if words else None,'reference_characters':chars,'reference_words':words},
            'alerts':{'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}}

def classification_metrics(rows, gold_key, predicted_key):
    """Report exact binary classifications; missing paired labels never become negatives."""
    import math
    tp=fp=fn=tn=0
    count=0
    for row in rows:
        if gold_key not in row and predicted_key not in row:
            continue
        if gold_key not in row or predicted_key not in row:
            raise ValueError(f'Incomplete {gold_key}/{predicted_key} evaluation pair')
        g,p=row[gold_key],row[predicted_key]
        if type(g) is not bool or type(p) is not bool:
            raise ValueError('Alert ground truth and predictions must be booleans')
        count+=1;tp+=int(g and p);fp+=int(not g and p)
        fn+=int(g and not p);tn+=int(not g and not p)
    return {'n':count,'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'accuracy':(tp+tn)/count if count else None,
            'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None}

def latency_metrics(rows):
    """Measured end-to-end timings, not model-loading estimates."""
    import math,statistics
    values=[]
    for row in rows:
        if 'elapsed_seconds' not in row:continue
        value=row['elapsed_seconds']
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('elapsed_seconds must be a finite nonnegative number')
        values.append(float(value))
    values.sort()
    if not values:return {'n':0,'median_s':None,'p95_s':None,'maximum_s':None}
    import math
    return {'n':len(values),'median_s':statistics.median(values),
            'p95_s':values[math.ceil(.95*len(values))-1],
            'maximum_s':values[-1]}

def evaluate_readiness(records, *, expected_split='test'):
    """Check whether reported accuracy can legitimately support thesis acceptance.

    This is a data-quality gate, not an accuracy score. A record without
    independent human adjudication is not valid evidence of model performance.
    """
    rows=list(records)
    if not rows: raise ValueError('No evaluation records')
    issues=[]
    seen=set()
    for idx, row in enumerate(rows,1):
        image_id=row.get('image_id')
        if not image_id: issues.append(f'row {idx}: missing image_id')
        elif image_id in seen: issues.append(f'row {idx}: duplicate image_id {image_id}')
        else: seen.add(image_id)
        if row.get('split') != expected_split:
            issues.append(f'row {idx}: not in independent {expected_split} split')
        if row.get('human_verified') is not True:
            issues.append(f'row {idx}: ground truth not human verified')
        if row.get('reviewer_id') in (None,''):
            issues.append(f'row {idx}: reviewer identifier missing')
        if not isinstance(row.get('gold'),dict) or not isinstance(row.get('predicted'),dict):
            issues.append(f'row {idx}: gold/predicted field dictionaries required')
    return {'ready':not issues,'records':len(rows),'issues':issues}


def evaluate_verified_jsonl(path, *, expected_split='test'):
    with open(path,encoding='utf-8') as stream:
        rows=[json.loads(line) for line in stream if line.strip()]
    readiness=evaluate_readiness(rows,expected_split=expected_split)
    if not readiness['ready']:
        return {'readiness':readiness,'metrics':None,'thesis_targets_met':False}
    metrics=evaluate(rows)
    f=metrics['fields']; alerts=metrics['alerts']; ocr=metrics['ocr']
    criteria={
        'medicine_accuracy_90pct':f['medicine']['accuracy'] is not None and f['medicine']['accuracy']>=.90,
        'dose_accuracy_90pct':f['dose']['accuracy'] is not None and f['dose']['accuracy']>=.90,
        'CER_max_10pct':ocr['CER'] is not None and ocr['CER']<=.10,
        'alert_precision_85pct':alerts['precision'] is not None and alerts['precision']>=.85,
        'alert_recall_85pct':alerts['recall'] is not None and alerts['recall']>=.85,
        'age_accuracy_85pct':metrics['age_alerts']['accuracy'] is not None and metrics['age_alerts']['accuracy']>=.85,
        'processing_p95_max_10s':metrics['timing']['p95_s'] is not None and metrics['timing']['n']==len(rows) and metrics['timing']['p95_s']<=10.0,
    }
    return {'readiness':readiness,'metrics':metrics,'criteria':criteria,
            'thesis_targets_met':all(criteria.values())}


def evaluate_jsonl(path):
    with open(path,encoding='utf-8') as stream: return evaluate(json.loads(line) for line in stream if line.strip())
