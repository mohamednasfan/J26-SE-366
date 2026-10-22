"""Unlabeled OCR prescription candidates must preserve uncertainty."""
from medsafe.extraction import extract_unlabeled_candidates

def test_prn_schedule_does_not_become_fixed_daily_frequency():
    result=extract_unlabeled_candidates("Tab FictionalMed 200 mg BID PRN")[0]
    assert result["candidate_only"] is True
    assert result["fields"]["frequency"]==""
    assert result["fields"]["dose"]==""
    assert result["fields"]["strength"].lower()=="200 mg"
    assert "AS_NEEDED_FREQUENCY_UNRESOLVED" in result["candidate_flags"]
    assert result["raw_source_line"]=="Tab FictionalMed 200 mg BID PRN"

def test_conflicting_frequency_in_candidate_is_not_autoselected():
    result=extract_unlabeled_candidates("Tab FictionalMed 200 mg BID TID")[0]
    assert "AMBIGUOUS_FREQUENCY_MENTIONS" in result["candidate_flags"]
    assert result["fields"]["frequency"]==""
    assert result["fields"]["dose"]==""
