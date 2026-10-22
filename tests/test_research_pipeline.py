import json
from pathlib import Path
import pytest

from backend.app.research.synthetic import generate
from backend.app.research.benchmark import read_manifest,run_benchmark
from medsafe.evaluation import evaluate, evaluate_verified_jsonl

def test_synthetic_dataset_is_deterministic_and_unverified(tmp_path):
    metadata=generate(tmp_path/'synthetic',count=6,seed=19,allow_small=True)
    assert metadata['count']==6
    rows=[json.loads(x) for x in (tmp_path/'synthetic'/'manifest.jsonl').read_text().splitlines()]
    assert len(rows)==6 and len({r['image_id'] for r in rows})==6
    assert all(r['human_verified'] is False for r in rows)
    assert all(r['dataset']=='SYNTHETIC_FICTIONAL_NOT_CLINICAL' for r in rows)
    assert all((tmp_path/'synthetic'/r['image_path']).is_file() for r in rows)
    with pytest.raises(ValueError,match='human-verification'):
        read_manifest(tmp_path/'synthetic'/'manifest.jsonl')

def test_benchmark_allows_explicit_synthetic_development_mode(tmp_path,monkeypatch):
    root=tmp_path/'synthetic';generate(root,count=3,seed=30,allow_small=True)
    def fake_recognize(data,engine):
        return {'text':'Age: 20 years\nMedicine: SYNTHMED-01\nDose: 25 mg',
                'engine':engine,'warnings':['SYNTHETIC_STUB']}
    monkeypatch.setattr('backend.app.research.benchmark.recognize',fake_recognize)
    result=run_benchmark(root/'manifest.jsonl',engines=['tesseract'],require_human=False)
    assert result['engines']['tesseract']['coverage']==1
    assert result['engines']['tesseract']['thesis_eligible'] is False
    assert result['engines']['tesseract']['metrics']['n']==3
    assert result['engines']['tesseract']['timing']['p95_s']>=0

def test_age_and_latency_metrics_and_acceptance_gate(tmp_path):
    item=dict(image_id='one',split='test',reviewer_id='independent-reviewer',
              human_verified=True,gold={'medicine':'X','dose':'1 mg'},
              predicted={'medicine':'X','dose':'1 mg'},
              gold_transcript='X dose 1 mg',predicted_transcript='X dose 1 mg',
              gold_alert=True,predicted_alert=True,gold_age_flag=False,
              predicted_age_flag=False,elapsed_seconds=1.2)
    manifest=tmp_path/'result.jsonl'
    manifest.write_text(json.dumps(item)+'\n')
    result=evaluate_verified_jsonl(manifest)
    assert result['metrics']['age_alerts']['accuracy']==1
    assert result['criteria']['age_accuracy_85pct'] is True
    assert result['criteria']['processing_p95_max_10s'] is True
    assert result['thesis_targets_met'] is True

def test_missing_age_and_timing_fail_criteria(tmp_path):
    row=dict(image_id='one',split='test',reviewer_id='reviewer',human_verified=True,
             gold={'medicine':'X','dose':'1 mg'},predicted={'medicine':'X','dose':'1 mg'},
             gold_transcript='X',predicted_transcript='X',
             gold_alert=True,predicted_alert=True)
    path=tmp_path/'missing.jsonl';path.write_text(json.dumps(row)+'\n')
    result=evaluate_verified_jsonl(path)
    assert result['criteria']['age_accuracy_85pct'] is False
    assert result['criteria']['processing_p95_max_10s'] is False
    assert result['thesis_targets_met'] is False

def test_incomplete_age_pair_rejected():
    with pytest.raises(ValueError,match='Incomplete'):
        evaluate([{'gold':{},'predicted':{},'gold_age_flag':True}])
