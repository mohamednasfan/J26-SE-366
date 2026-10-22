"""Reviewed clinical screen must abstain on incomplete or contradictory prescriptions."""
import json
from medsafe.pipeline import analyze_text
from backend.app.services.review_service import assess_report

RULE = {
    "ingredient":"FictionalTest","product_identifier":"TEST-0001",
    "route":"oral","indication":"synthetic test","population":"fictional adult",
    "dose_unit":"mg","max_single":100,"max_daily":200,
    "source_url":"https://example.org/fictional","source_section":"synthetic",
    "reviewer":"unit test","review_date":"2026-01-01","version":"1",
    "review_status":"APPROVED_BY_QUALIFIED_REVIEWER",
    "min_age_years":18,"max_age_years":65,
}

BASE = ("Medicine: FictionalTest\nProduct Identifier: TEST-0001\n"
        "Route: oral\nIndication: synthetic test\n"
        "Population: fictional adult\n")

def _analyze(monkeypatch,tmp_path,text):
    file=tmp_path/"fixture.json"
    file.write_text(json.dumps([RULE]),encoding="utf-8")
    monkeypatch.setenv("MEDSAFE_REVIEWED_RULES",str(file))
    return assess_report(analyze_text(text))

def test_conflicting_frequency_must_not_trigger_threshold_flag(monkeypatch,tmp_path):
    report=_analyze(monkeypatch,tmp_path,BASE+"Dose: 500 mg\nFrequency: BID\nFrequency: TID\nAge: 20 years")
    m=report["medications"][0]
    assert m["reviewed_dose_rule"]["status"]=="NOT_EVALUATED"
    assert m["reviewed_age_rule"]["status"]=="UNABLE_TO_VALIDATE"
    assert not m["dose_validation_available"]
    assert "REVIEWED_RULE_THRESHOLD_EXCEEDED" not in {x["code"] for x in report["issues"]}
    assert report["clinical_clearance"] is False

def test_missing_dose_blocks_reviewed_age_screen(monkeypatch,tmp_path):
    report=_analyze(monkeypatch,tmp_path,BASE+"Frequency: twice daily\nAge: 10 years")
    m=report["medications"][0]
    assert m["reviewed_age_rule"]["status"]=="UNABLE_TO_VALIDATE"
    assert m["reviewed_dose_rule"]["status"]=="NOT_EVALUATED"

def test_complete_fictional_fixture_can_trigger_advisory_not_clearance(monkeypatch,tmp_path):
    report=_analyze(monkeypatch,tmp_path,BASE+"Dose: 500 mg\nFrequency: BID\nAge: 10 years")
    m=report["medications"][0]
    assert m["reviewed_dose_rule"]["status"]=="REVIEW_THRESHOLD_EXCEEDED"
    assert m["reviewed_age_rule"]["status"]=="REVIEW_AGE_RANGE_FLAG"
    assert report["clinical_clearance"] is False
    assert report["can_auto_dispense"] is False
