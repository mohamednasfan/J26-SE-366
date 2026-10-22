"""Clinical release gates must never claim approval from software evidence."""
import json
from backend.app.research.clinical_readiness import clinical_readiness

def test_missing_clinical_artifacts_block_release(tmp_path):
    result=clinical_readiness(tmp_path/"missing-rules.json",tmp_path/"missing-evaluation.json",tmp_path/"missing-approval.json")
    assert result["clinical_use_authorized"] is False
    assert "RULE_REGISTRY_INVALID_OR_UNAVAILABLE" in result["blockers"]
    assert "DOCUMENTED_CLINICAL_SIGNOFF_MISSING" in result["blockers"]

def test_empty_rules_and_synthetic_evaluation_block_release(tmp_path):
    registry=tmp_path/"rules.json"
    registry.write_text("[]",encoding="utf-8")
    evaluation=tmp_path/"evaluation.json"
    evaluation.write_text(json.dumps({"label_policy":"SYNTHETIC_DEVELOPMENT_ONLY_NOT_THESIS_EVIDENCE","engines":{"tesseract":{"thesis_eligible":True}}}),encoding="utf-8")
    approval=tmp_path/"approval.json"
    approval.write_text("{}",encoding="utf-8")
    result=clinical_readiness(registry,evaluation,approval)
    assert result["reviewed_rule_count"]==0
    assert result["clinical_use_authorized"] is False
    assert "NO_APPROVED_REAL_DRUG_RULES" in result["blockers"]
    assert "INDEPENDENT_HUMAN_LABELED_EVALUATION_MISSING" in result["blockers"]

def test_apparent_signoff_is_not_automatically_authenticated(tmp_path):
    registry=tmp_path/"rules.json"
    registry.write_text("[]",encoding="utf-8")
    evaluation=tmp_path/"evaluation.json"
    evaluation.write_text(json.dumps({"label_policy":"HUMAN_VERIFIED_TEST_ONLY","engines":{"tesseract":{"thesis_eligible":True}}}),encoding="utf-8")
    approval=tmp_path/"approval.json"
    approval.write_text(json.dumps({key:"example" for key in (
        "reviewer_name","reviewer_credentials","independent_reviewer",
        "institution","approval_reference","approval_date"
    )}),encoding="utf-8")
    result=clinical_readiness(registry,evaluation,approval)
    assert result["clinical_use_authorized"] is False
    assert result["independent_governance_verification_required"] is True
    assert "SIGNATURE_AND_GOVERNANCE_AUTHENTICITY_REQUIRES_EXTERNAL_VERIFICATION" in result["blockers"]
