from medsafe.metadata import extract_metadata
from medsafe.pipeline import analyze_text

def test_complete_metadata():
 text='Hospital: Example Clinic\nDoctor: Dr Example\nPatient: Example\nAge: 30\nDate: 2026-10-21\nMedicine: DEMO-DRUG-A\nDose: 100 mg\nFrequency: twice daily'
 result=analyze_text(text)
 f=result['prescription_details']['fields']
 assert f['hospital_name']=='Example Clinic'
 assert f['doctor_name']=='Dr Example'
 assert f['patient_name']=='Example'
 assert f['prescription_date']=='2026-10-21'
 assert result['clinical_clearance'] is False

def test_missing_fields_are_null_not_invented():
 d=extract_metadata('Tab Napa\nRivotril')
 assert all(v is None for v in d['fields'].values())
 assert d['human_review_required'] and not d['signature_authenticated']

def test_conflicting_doctors_block():
 r=analyze_text('Doctor: Dr A\nDoctor: Dr B\nMedicine: DEMO-DRUG-A\nDose: 100 mg\nFrequency: daily\nAge: 30')
 assert r['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
 assert any(x['code']=='CONFLICTING_PRESCRIPTION_DETAILS' for x in r['issues'])

def test_bad_date_does_not_pass():
 d=extract_metadata('Date: 2026-99-99')
 assert d['fields']['prescription_date'] is None
 assert d['conflicts'][0]['issue']=='UNRECOGNIZED_DATE_FORMAT'
