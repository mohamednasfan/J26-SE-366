from fastapi.testclient import TestClient
from medsafe.api import app
client=TestClient(app)
def test_review_import_fail_closed():
    p={'schema':'medsafe.review_only_ocr.v1','transcription_for_review':'Tiz','regions':[]}
    r=client.post('/api/review/import',json=p)
    assert r.status_code==200
    assert r.json()['clinical_clearance'] is False
    assert r.json()['can_auto_dispense'] is False
    assert client.post('/api/review/import',json={**p,'clinical_clearance':True}).status_code==422
def test_confirmation_required():
    assert client.post('/api/review/submit',json={'corrected_transcription':'medicine: example','reviewer_confirmed':False}).status_code==422
def test_review_page():
    assert client.get('/review').status_code==200
