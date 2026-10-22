from medsafe.evaluation import evaluate_readiness, evaluate_verified_jsonl
import json

def test_unverified_is_not_acceptance(tmp_path):
    p=tmp_path/'eval.jsonl'
    p.write_text(json.dumps({'gold':{'medicine':'A'},'predicted':{'medicine':'A'},'gold_alert':False,'predicted_alert':False})+'\n')
    result=evaluate_verified_jsonl(p)
    assert result['thesis_targets_met'] is False
    assert result['metrics'] is None
    assert result['readiness']['issues']

def test_duplicate_ids_are_rejected():
    row={'image_id':'one','split':'test','human_verified':True,'reviewer_id':'R1','gold':{},'predicted':{}}
    assert not evaluate_readiness([row,row])['ready']

def test_valid_row_is_ready():
    row={'image_id':'one','split':'test','human_verified':True,'reviewer_id':'R1','gold':{},'predicted':{}}
    assert evaluate_readiness([row])['ready']
