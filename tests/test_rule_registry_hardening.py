import json
import pytest
from medsafe.rule_registry import RuleRegistryError, load_reviewed_rules, match_rule, assess_reviewed_rule

def rule():
    return dict(ingredient="fictional-test-med",product_identifier="TEST-PRODUCT-001",
        route="oral",indication="synthetic experiment",population="adult research fixture",
        dose_unit="mg",max_single=100.0,max_daily=200.0,
        source_url="https://example.org/synthetic-fixture",source_section="synthetic only",
        reviewer="test reviewer",review_date="2026-01-01",version="1",
        review_status="APPROVED_BY_QUALIFIED_REVIEWER",min_age_years=18,max_age_years=65)

def load(tmp_path, rules):
    path=tmp_path/"rules.json"
    path.write_text(json.dumps(rules))
    return load_reviewed_rules(path)

def test_empty_registry(tmp_path):
    assert load(tmp_path,[])==[]

@pytest.mark.parametrize("bad",[float("nan"),float("inf"),float("-inf"),True,0,-1])
def test_reject_invalid_thresholds(tmp_path,bad):
    item=rule();item["max_daily"]=bad
    with pytest.raises(RuleRegistryError):load(tmp_path,[item])

def test_future_review_date(tmp_path):
    item=rule();item["review_date"]="2999-01-01"
    with pytest.raises(RuleRegistryError):load(tmp_path,[item])

def test_invalid_age_range(tmp_path):
    item=rule();item["min_age_years"]=80
    with pytest.raises(RuleRegistryError):load(tmp_path,[item])

def test_duplicate_context(tmp_path):
    item=rule()
    with pytest.raises(RuleRegistryError):load(tmp_path,[item,item])

def test_missing_context_cannot_match():
    assert match_rule([rule()],ingredient="fictional-test-med",product_identifier="",
        route="oral",indication="synthetic experiment",population="adult research fixture") is None

def test_threshold_flag_not_clearance():
    outcome=assess_reviewed_rule(rule(),dose=110,unit="mg",frequency=2)
    assert outcome["status"]=="REVIEW_THRESHOLD_EXCEEDED"
    assert outcome["clinical_clearance"] is False

def test_below_threshold_not_safe():
    outcome=assess_reviewed_rule(rule(),dose=20,unit="mg",frequency=1)
    assert outcome["status"]=="BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY"
    assert outcome["clinical_clearance"] is False

@pytest.mark.parametrize("dose",[float("nan"),float("inf"),True,-5])
def test_invalid_dose_not_evaluated(dose):
    assert assess_reviewed_rule(rule(),dose=dose,unit="mg",frequency=2)["status"]=="NOT_EVALUATED"
