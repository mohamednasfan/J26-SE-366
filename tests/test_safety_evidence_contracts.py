"""Clinical research thresholds: exact source context and physical mass units."""
import json
from datetime import date

from medsafe.rule_registry import assess_reviewed_rule
from medsafe.pipeline import analyze_text
from medsafe.api_product import _rule_assessment
from medsafe.references import lookup


def test_mass_conversion_is_dimensionally_safe_and_traceable():
    rule={
        "dose_unit":"mg","max_single":400.0,"max_daily":800.0,
        "source_url":"https://example.org/fictional","reviewer":"fixture",
        "version":"1","review_status":"APPROVED_BY_QUALIFIED_REVIEWER",
    }
    result=assess_reviewed_rule(rule,dose=.5,unit="g",frequency=2)
    assert result["status"]=="REVIEW_THRESHOLD_EXCEEDED"
    assert result["dose_unit"]=="mg"
    assert result["administered_single"]==500
    assert result["administered_daily"]==1000
    assert result["reported_unit"]=="g"
    assert result["clinical_clearance"] is False
    assert assess_reviewed_rule(rule,dose=.5,unit="mL",frequency=2)["status"]=="NOT_EVALUATED"


def test_invalid_patient_age_not_used_in_reviewed_age_screen(tmp_path,monkeypatch):
    rule={
        "ingredient":"SYNTHMED-01","product_identifier":"FICT-01",
        "route":"oral","indication":"fictional simulation",
        "population":"synthetic test","dose_unit":"mg",
        "max_single":100.0,"max_daily":200.0,
        "min_age_years":12,"max_age_years":65,
        "source_url":"https://example.org/fictional-source",
        "source_section":"research only","reviewer":"test fixture",
        "review_date":date.today().isoformat(),"version":"1",
        "review_status":"APPROVED_BY_QUALIFIED_REVIEWER",
    }
    path=tmp_path/"rules.json"
    path.write_text(json.dumps([rule]))
    monkeypatch.setenv("MEDSAFE_REVIEWED_RULES",str(path))
    report=_rule_assessment(analyze_text(
        "Medicine: SYNTHMED-01\nDose: 50 mg\nFrequency: twice daily\nAge: 130 years\n"
        "Route: oral\nProduct Identifier: FICT-01\n"
        "Indication: fictional simulation\nPopulation: synthetic test"
    ))
    assert report["medications"][0]["reviewed_age_rule"]["status"]=="UNABLE_TO_VALIDATE"
    assert "INVALID_AGE" in {issue["code"] for issue in report["issues"]}
    assert report["clinical_clearance"] is False


def test_unavailable_rule_registry_is_explicitly_reported(tmp_path,monkeypatch):
    monkeypatch.setenv("MEDSAFE_REVIEWED_RULES",str(tmp_path/"missing.json"))
    report=_rule_assessment(analyze_text(
        "Medicine: Example\nDose: 50 mg\nFrequency: once daily\nAge: 30 years"
    ))
    assert report["reviewed_rule_registry_status"]=="INVALID_OR_UNAVAILABLE"
    assert "REVIEWED_RULE_REGISTRY_UNAVAILABLE" in {x["code"] for x in report["issues"]}


def test_overdosage_from_openfda_is_only_label_evidence():
    class Response:
        status_code=200
        def __init__(self,value): self.value=value
        def raise_for_status(self): pass
        def json(self): return self.value

    class Session:
        def get(self,url,**kwargs):
            if "dailymed" in url:
                return Response({"data":[]})
            if "fda.gov" in url:
                return Response({"results":[{
                    "openfda":{"generic_name":["ExampleMed"]},
                    "set_id":"fictitious-set-id-12345",
                    "overdosage":["FICTIONAL: sample adverse effect description."],
                    "pediatric_use":["FICTIONAL: age considerations."]
                }]})
            return Response({"idGroup":{"rxnormId":[]}})
    result=lookup("ExampleMed",session=Session())
    assert result["dose_threshold_extracted"] is False
    assert result["openfda"][0]["label_sections_UNVERIFIED_FOR_PRODUCT"]["overdosage"].startswith("FICTIONAL:")
