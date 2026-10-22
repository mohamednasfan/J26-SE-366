"""Regression tests for side-by-side preview and intentionally unverified text metrics."""
import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.api.routes import ocr_compare
from medsafe.api_product import app


def _image_bytes():
    image=Image.new('RGB',(260,140),'white')
    buf=io.BytesIO()
    image.save(buf,format='PNG')
    return buf.getvalue()


def test_four_engine_comparison_returns_fields_and_timing(monkeypatch):
    calls=[]
    transcript='Medicine: DEMO\nDose: 20 mg\nFrequency: twice daily\nAge: 40 years\nRoute: oral'
    def mock_recognize(data, *, engine):
        calls.append((data,engine))
        if engine=='paddleocr':
            return {'text':'Medicine: DEMO\nDose: 20 mg','regions':[{'box':[5,5,70,25]}],
                    'warnings':['OCR_NOT_VERIFIED']}
        if engine=='craft_trocr':
            raise ocr_compare.OCRUnavailable('Notebook 44 checkpoint not mounted')
        return {'text':transcript,'regions':[{'box':[5,5,70,25]}],'warnings':[]}
    monkeypatch.setattr(ocr_compare,'recognize',mock_recognize)
    r=TestClient(app).post('/api/compare?preprocess=none',
        files={'file':('fictional.png',_image_bytes(),'image/png')},
        data={'reference_text':transcript})
    assert r.status_code==200,r.text
    body=r.json()
    assert body['completed_engines']==3 and body['n_engines']==4
    assert body['clinical_clearance'] is False
    assert body['valid_thesis_accuracy_result'] is False
    assert body['reference_independently_verified'] is False
    assert len(calls)==4
    assert len({row[0] for row in calls})==1
    assert [row[1] for row in calls]==list(ocr_compare.ENGINES)
    tess=body['engines']['tesseract']
    assert tess['reference_metrics']['cer']==0
    assert tess['reference_metrics']['wer']==0
    assert tess['reference_metrics']['valid_thesis_accuracy_result'] is False
    assert tess['extraction']['field_coverage']['detected']==5
    assert tess['extraction']['medications'][0]['fields']['dose']=='20 mg'
    assert body['engines']['paddleocr']['extraction']['field_coverage']['detected']==2
    assert body['engines']['paddleocr']['reference_metrics']['cer']>0
    assert body['engines']['craft_trocr']['status']=='UNAVAILABLE'
    assert 'checkpoint' in body['engines']['craft_trocr']['reason']


def test_no_reference_does_not_fabricate_accuracy(monkeypatch):
    monkeypatch.setattr(ocr_compare,'recognize',
        lambda data,*,engine:{'text':'Medicine: Demo','regions':[],'warnings':[]})
    r=TestClient(app).post('/api/compare',files={'file':('demo.png',_image_bytes(),'image/png')})
    assert r.status_code==200,r.text
    body=r.json()
    assert body['reference_used'] is False
    assert all(item['reference_metrics'] is None for item in body['engines'].values())
    assert body['has_independent_ground_truth'] is False


def test_unlabeled_strength_never_becomes_administered_dose():
    p=ocr_compare.preview_extraction('Tab Example 100 mg BD')
    med=p['medications'][0]
    assert med['candidate_only'] is True
    assert med['fields']['dose']==''
    assert med['fields']['strength']=='100 mg'
    assert 'dose' in med['missing_fields']
    assert p['clinical_clearance'] is False


def test_reference_too_long_rejected_without_model_inference(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('recognition should not have run')
    monkeypatch.setattr(ocr_compare,'recognize',forbidden)
    r=TestClient(app).post('/api/compare',
        files={'file':('demo.png',_image_bytes(),'image/png')},
        data={'reference_text':'a'*12001})
    assert r.status_code==422
