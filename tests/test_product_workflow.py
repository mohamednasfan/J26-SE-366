import io, os
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    import medsafe.storage as storage
    monkeypatch.setattr(storage,'DATA',tmp_path)
    from medsafe.api_product import app
    return TestClient(app)

def _image():
    im=Image.new('RGB',(730,280),'white')
    d=ImageDraw.Draw(im)
    for i,text in enumerate(['Medicine: TEST','Dose: 50 mg','Frequency: twice daily','Age: 45 years']):d.text((35,45+i*49),text,fill='black')
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def test_static_app_and_status(client):
    assert client.get('/').status_code==200
    assert 'PRESCRIPTION INTELLIGENCE' in client.get('/').text
    assert client.get('/offline/app.js').status_code==200
    assert client.get('/api/health').json()['clinical_clearance'] is False
    assert client.get('/api/models').json()['default']=='tesseract'

def test_upload_review_report_history_delete(client):
    r=client.post('/api/prescriptions?engine=tesseract',files={'file':('test.png',_image(),'image/png')})
    assert r.status_code==200,r.text
    body=r.json();pid=body['id']
    assert body['clinical_clearance'] is False
    assert client.get(f'/api/prescriptions/{pid}/image').status_code==200
    assert client.get(f'/api/prescriptions/{pid}/report').status_code==409
    payload={'corrected_text':'Age: 45 years\nMedicine: Aspirin\nDose: 50 mg\nFrequency: twice daily\nRoute: oral','reviewer_confirmed':True}
    r=client.post(f'/api/prescriptions/{pid}/review',json=payload)
    assert r.status_code==200,r.text
    report=r.json()['report']
    assert report['dose_safety_summary']=='UNABLE_TO_VALIDATE'
    assert report['age_safety_summary']=='UNABLE_TO_VALIDATE'
    assert not report['clinical_clearance'] and not report['can_auto_dispense']
    assert report['medications'][0]['reviewed_dose_rule']['status']=='NOT_EVALUATED'
    assert client.get('/api/stats').json()['reviewed']==1
    assert client.get(f'/api/prescriptions/{pid}/report').status_code==200
    assert client.delete(f'/api/prescriptions/{pid}').json()['deleted']
    assert client.get(f'/api/prescriptions/{pid}').status_code==404

def test_review_requires_confirmation_and_nonempty(client):
    r=client.post('/api/prescriptions?engine=tesseract',files={'file':('demo.png',_image(),'image/png')})
    pid=r.json()['id']
    assert client.post(f'/api/prescriptions/{pid}/review',json={'corrected_text':'Medicine: aspirin','reviewer_confirmed':False}).status_code==422
    assert client.post(f'/api/prescriptions/{pid}/review',json={'corrected_text':'','reviewer_confirmed':True}).status_code==422

def test_unsafe_image_rejected(client):
    assert client.post('/api/prescriptions',files={'file':('x.csv',b'abc','text/csv')}).status_code==415
    assert client.post('/api/prescriptions?engine=tesseract',files={'file':('x.png',b'not_image','image/png')}).status_code==422

def test_craft_pipeline_no_hardcoded_boxes(monkeypatch):
    import medsafe.ocr_product as p
    im=Image.new('RGB',(200,150),'white');b=io.BytesIO();im.save(b,format='PNG')
    monkeypatch.setattr(p,'checkpoint_status',lambda:{'ready_for_load':True})
    monkeypatch.setattr(p,'_boxes',lambda image:[(12,20,170,43),(7,78,155,110)])
    monkeypatch.setattr(p,'_trocr_lines',lambda image,boxes:['Medicine: Example','Dose: 5 mg'])
    r=p.recognize(b.getvalue())
    assert r['text']=='Medicine: Example\nDose: 5 mg'
    assert r['engine']=='craft_trocr' and all(not x['verified'] for x in r['regions'])
    assert r['confidence'] is None


def test_unapproved_reference_never_clears_dose(client):
    from medsafe.pipeline import analyze_text
    report=analyze_text('Medicine: Amoxicillin\nDose: 500 mg\nAge: 42 years\nFrequency: twice daily\nRoute: oral')
    assert report['checks']['dose_safety']=='NO_VERIFIED_DRUG_SPECIFIC_RULE'
    assert not report['clinical_clearance']

def test_reviewed_rule_age_and_dose_flags_only_on_exact_match(client,tmp_path,monkeypatch):
    import json
    from datetime import date
    from medsafe.api_product import _rule_assessment
    rule={'ingredient':'EXAMPLEMED','product_identifier':'PRODUCT-123',
          'route':'oral','indication':'synthetic test','population':'adult',
          'dose_unit':'mg','max_single':10.0,'max_daily':20.0,
          'min_age_years':18.0,'max_age_years':65.0,
          'source_url':'https://example.com/synthetic-test','source_section':'Mock test only',
          'reviewer':'mock tester','review_date':date.today().isoformat(),'version':'test1',
          'review_status':'APPROVED_BY_QUALIFIED_REVIEWER'}
    rules_path=tmp_path/'rules.json';rules_path.write_text(json.dumps([rule]))
    monkeypatch.setenv('MEDSAFE_REVIEWED_RULES',str(rules_path))
    from medsafe.pipeline import analyze_text
    text='Age: 70 years\nMedicine: EXAMPLEMED\nDose: 50 mg\nFrequency: twice daily\nRoute: oral\nProduct Identifier: PRODUCT-123\nIndication: synthetic test\nPopulation: adult'
    rep=_rule_assessment(analyze_text(text))
    assert rep['medications'][0]['reviewed_dose_rule']['status']=='REVIEW_THRESHOLD_EXCEEDED'
    assert rep['medications'][0]['reviewed_age_rule']['status']=='REVIEW_AGE_RANGE_FLAG'
    assert 'REVIEWED_RULE_THRESHOLD_EXCEEDED' in {i['code'] for i in rep['issues']}
    rep2=_rule_assessment(analyze_text(text.replace('PRODUCT-123','WRONG-ID')))
    assert rep2['medications'][0]['reviewed_dose_rule']['status']=='NOT_EVALUATED'
    assert rep2['medications'][0]['reviewed_age_rule']['status']=='UNABLE_TO_VALIDATE'
