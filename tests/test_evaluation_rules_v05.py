import json
import pytest
from medsafe.evaluation import evaluate,edit_distance
from medsafe.rule_registry import load_reviewed_rules,match_rule,assess_reviewed_rule,RuleRegistryError

def test_cer_wer_and_fields():
    r=evaluate([{'gold':{'medicine':'ABC','dose':'10 mg'},'predicted':{'medicine':'abc','dose':'20 mg'},'gold_transcript':'ABC X','predicted_transcript':'ABC Y','gold_alert':True,'predicted_alert':False}])
    assert r['fields']['medicine']['accuracy']==1
    assert r['fields']['dose']['accuracy']==0
    assert r['ocr']['CER']==0.2 and r['ocr']['WER']==0.5
    assert r['alerts']['fn']==1 and r['alerts']['recall']==0

def test_empty_dataset_rejected():
    with pytest.raises(ValueError): evaluate([])

def test_empty_rule_registry(tmp_path):
    p=tmp_path/'r.json';p.write_text('[]');assert load_reviewed_rules(p)==[]

def test_unreviewed_rules_rejected(tmp_path):
    p=tmp_path/'r.json';p.write_text(json.dumps([{'ingredient':'a'}]))
    with pytest.raises(RuleRegistryError):load_reviewed_rules(p)

def test_exact_context_required():
    r={'ingredient':'x','product_identifier':'id','route':'oral','indication':'a','population':'adult','dose_unit':'mg','max_single':10,'max_daily':20,'source_url':'https://example.org','reviewer':'reviewer','version':'1'}
    assert match_rule([r],ingredient='x',product_identifier='id',route='iv',indication='a',population='adult') is None
    assert assess_reviewed_rule(r,dose=15,unit='mg',frequency=2)['status']=='REVIEW_THRESHOLD_EXCEEDED'
    assert assess_reviewed_rule(r,dose=5,unit='ml',frequency=2)['status']=='NOT_EVALUATED'
    assert assess_reviewed_rule(r,dose=5,unit='mg',frequency=2)['clinical_clearance'] is False
