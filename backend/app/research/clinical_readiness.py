"""Conservative clinical evidence gate. Never creates professional approval.

This gate checks artifact completeness, not authenticity or clinical correctness.
A human governance process must validate signatures and source documents.
"""
from __future__ import annotations
import json
from pathlib import Path

def clinical_readiness(registry_path, evaluation_path, approval_path):
    blockers = []
    try:
        from medsafe.rule_registry import load_reviewed_rules
        rules = load_reviewed_rules(registry_path)
        if not rules:
            blockers.append("NO_APPROVED_REAL_DRUG_RULES")
        if any(str(r.get("ingredient", "")).lower().startswith(("synthmed", "fictional", "test-")) for r in rules):
            blockers.append("SYNTHETIC_RULES_CANNOT_VALIDATE_CLINICAL_READINESS")
    except (OSError, ValueError, TypeError) as exc:
        rules = []
        blockers.append("RULE_REGISTRY_INVALID_OR_UNAVAILABLE")
    try:
        evaluation = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
        if not isinstance(evaluation, dict) or evaluation.get("label_policy") != "HUMAN_VERIFIED_TEST_ONLY":
            blockers.append("INDEPENDENT_HUMAN_LABELED_EVALUATION_MISSING")
        engines = evaluation.get("engines", {}) if isinstance(evaluation, dict) else {}
        if not engines or not all(
            isinstance(v, dict) and v.get("thesis_eligible") is True
            for v in engines.values()
        ):
            blockers.append("CLINICAL_EVALUATION_TARGETS_NOT_ESTABLISHED")
    except (OSError, ValueError, TypeError):
        blockers.append("EVALUATION_ARTIFACT_MISSING_OR_INVALID")
    try:
        approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
        required = ("reviewer_name", "reviewer_credentials", "independent_reviewer",
                    "institution", "approval_reference", "approval_date")
        if not isinstance(approval, dict) or any(
            not isinstance(approval.get(key), str) or not approval[key].strip()
            for key in required
        ):
            blockers.append("DOCUMENTED_CLINICAL_SIGNOFF_MISSING")
        # A filled-in record is NOT independently authenticated by this script.
        blockers.append("SIGNATURE_AND_GOVERNANCE_AUTHENTICITY_REQUIRES_EXTERNAL_VERIFICATION")
    except (OSError, ValueError, TypeError):
        blockers.append("DOCUMENTED_CLINICAL_SIGNOFF_MISSING")
    return {
        "clinical_use_authorized": False,
        "automated_evidence_checks_passed": not any(
            b != "SIGNATURE_AND_GOVERNANCE_AUTHENTICITY_REQUIRES_EXTERNAL_VERIFICATION"
            for b in blockers
        ),
        "independent_governance_verification_required": True,
        "reviewed_rule_count": len(rules),
        "blockers": sorted(set(blockers)),
        "message": "Software evidence checks never grant clinical-use authorization.",
    }
