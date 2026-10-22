"""Regression tests for model integration (not a substitute for running 1.3-GB checkpoint)."""
import io
import json
from pathlib import Path
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from medsafe.api import app
from medsafe.extraction import extract_prescription
from medsafe.pipeline import analyze_text, analyze_image
from medsafe import trocr
from medsafe import ocr


def test_two_distinct_prescriptions_preserve_dose_ownership():
    text='''Age: 13
Medicine: DEMO-DRUG-A
Dose: 200 mg
Frequency: twice daily
Route: oral
Medicine: OtherDrug
Dose: 10 mg
Frequency: once daily
Route: oral'''
    v=analyze_text(text)
    assert v['medication_count']==2
    assert [x['extraction']['fields']['medicine'] for x in v['medications']]==['DEMO-DRUG-A','OtherDrug']
    assert [x['extraction']['fields']['dose'] for x in v['medications']]==['200 mg','10 mg']
    assert v['medications'][0]['checks']['dose_safety']=='WITHIN_SYNTHETIC_FIXTURE_ONLY'
    assert v['medications'][1]['checks']['dose_safety']=='NO_VERIFIED_DRUG_SPECIFIC_RULE'
    assert 'MULTIPLE_MEDICATIONS_INTERACTION_UNVERIFIED' in {x['code'] for x in v['issues']}
    assert not v['clinical_clearance']


def test_strength_not_prescribed_dose():
    a=analyze_text('Medicine: ExampleMedicine\nStrength: 500 mg\nFrequency: twice daily\nAge: 30')
    assert a['extraction']['fields']['strength']=='500 mg'
    assert a['extraction']['fields']['dose']==''
    assert 'MISSING_DOSE' in {x['code'] for x in a['issues']}


def test_trocr_requires_weights_and_never_silent_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv('MEDSAFE_TROCR_MODEL_DIR',str(tmp_path))
    state=trocr.checkpoint_status()
    assert state['ready_for_load'] is False
    im=Image.new('RGB',(300,100),'white');b=io.BytesIO();im.save(b,format='PNG')
    with TestClient(app) as c:
        assert c.get('/api/models').json()['active_engine_auto']=='tesseract'
        r=c.post('/api/analyze-image?engine=trocr',content=b.getvalue(),headers={'Content-Type':'image/png'})
    # Text segmentation may yield zero regions, so either empty blocked output or 503 is acceptable.
    assert r.status_code in (200,503)
    if r.status_code==200:
        assert r.json()['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
        assert r.json()['ocr']['engine']=='trocr_notebook44_finetuned'


def test_default_auto_uses_trained_adapter_when_ready(monkeypatch):
    monkeypatch.setattr(trocr,'checkpoint_status',lambda:{'ready_for_load':True})
    from medsafe import segments
    monkeypatch.setattr(segments,'propose_text_regions',lambda img:([img],[{'x1':0,'y1':0,'x2':img.width,'y2':img.height}]))
    monkeypatch.setattr(trocr,'infer_regions',lambda images:['Medicine: ExampleDrug\nDose: 10 mg\nFrequency: once daily\nAge: 30'])
    im=Image.new('RGB',(120,60),'white');b=io.BytesIO();im.save(b,format='PNG')
    answer=analyze_image(b.getvalue(),engine='auto')
    assert answer['ocr']['engine']=='trocr_notebook44_finetuned'
    assert answer['extraction']['fields']['medicine']=='ExampleDrug'
    assert answer['ocr']['confidence'] is None
    assert 'LOW_OCR_CONFIDENCE' in {x['code'] for x in answer['issues']}
    assert answer['status']=='BLOCKED_INVALID_OR_INCOMPLETE'


def test_model_files_detected_without_loading(monkeypatch, tmp_path):
    for f in ('config.json','model.safetensors','tokenizer.json','tokenizer_config.json','processor_config.json','preprocessor_config.json'):
        (tmp_path/f).write_text('fixture')
    monkeypatch.setenv('MEDSAFE_TROCR_MODEL_DIR',str(tmp_path))
    assert trocr.checkpoint_status()['ready_for_load'] is True


def test_multi_with_conflicting_shared_age_blocks_both():
    text='''Medicine: DrugA
Dose: 10 mg
Frequency: daily
Medicine: DrugB
Dose: 20 mg
Frequency: daily
Age: 30
Age: 10'''
    a=analyze_text(text)
    assert a['medication_count']==2
    assert all('CONFLICTING_FIELDS' in {e['code'] for e in m['issues']} for m in a['medications'])
    assert a['status']=='BLOCKED_INVALID_OR_INCOMPLETE'


def test_unrecognized_engine_rejected():
    im=Image.new('RGB',(200,100),'white');b=io.BytesIO();im.save(b,format='PNG')
    with pytest.raises(ValueError): ocr.ocr_image(b.getvalue(),engine='unconfigured')


def test_real_image_proposal_returns_bounded_geometry():
    from medsafe.segments import propose_text_regions
    im=Image.new('RGB',(760,250),'white');d=ImageDraw.Draw(im)
    d.text((30,40),'Medicine: DEMO-DRUG-A',fill='black')
    d.text((30,85),'Dose: 100 mg',fill='black')
    crops,xy=propose_text_regions(im)
    assert len(crops)==len(xy)
    assert all(0<=r['x1']<r['x2']<=760 and 0<=r['y1']<r['y2']<=250 for r in xy)


def test_explicit_incomplete_model_does_not_silently_fallback(monkeypatch,tmp_path):
    monkeypatch.setenv('MEDSAFE_TROCR_MODEL_DIR',str(tmp_path))
    image=Image.new('RGB',(170,90),'white'); b=io.BytesIO();image.save(b,format='PNG')
    with TestClient(app) as c:
        result=c.post('/api/analyze-image?engine=auto',content=b.getvalue(),headers={'content-type':'image/png'})
    assert result.status_code==503
    assert 'checkpoint' in result.json()['detail'].lower()


def test_duplicate_medication_regimen_blocks():
    text='''Age: 30
Medicine: DEMO-DRUG-A
Dose: 10 mg
Frequency: daily
Route: oral
Medicine: DEMO-DRUG-A
Dose: 500 mg
Frequency: twice daily
Route: oral'''
    result=analyze_text(text)
    assert result['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
    assert 'DUPLICATE_MEDICATION_REGIMEN' in {x['code'] for x in result['issues']}


def test_rxnorm_search_candidate_not_dose_verification():
    from medsafe.references import lookup
    class Response:
        status_code=200
        def __init__(self,d):self.d=d
        def raise_for_status(self):pass
        def json(self):return self.d
    class Session:
        def get(self,url,**kw):
            if 'rxnav' in url:return Response({'idGroup':{'rxnormId':['12345']}})
            if 'dailymed' in url:return Response({'data':[]})
            return Response({'results':[]})
    r=lookup('ExampleMed',session=Session())
    assert r['status']=='CANDIDATES_FOUND'
    assert r['rxnorm']['concept_ids']==['12345']
    assert r['dose_threshold_extracted'] is False


def test_trocr_word_crops_reconstruct_semantic_line(monkeypatch):
    import medsafe.segments as seg
    monkeypatch.setattr(seg,'propose_text_regions',lambda im:(
      [im,im,im,im],
      [{'x1':10,'y1':10,'x2':90,'y2':32},
       {'x1':100,'y1':10,'x2':180,'y2':32},
       {'x1':10,'y1':60,'x2':90,'y2':82},
       {'x1':100,'y1':60,'x2':180,'y2':82}] ))
    monkeypatch.setattr(trocr,'infer_regions',lambda images:['Medicine:','ExampleMed','Dose:','10 mg'])
    b=io.BytesIO();Image.new('RGB',(200,120),'white').save(b,format='PNG')
    result=ocr.ocr_image(b.getvalue(),engine='trocr')
    assert result['text']=='Medicine: ExampleMed\nDose: 10 mg'
    assert result['detected_line_count']==2


def test_top_level_finds_invalid_second_medicine():
    t='''Age: 30
Medicine: DEMO-DRUG-A
Dose: 100 mg
Frequency: twice daily
Route: oral
Medicine: OtherDrug
Dose: nonsense
Frequency: BID'''
    d=analyze_text(t)
    assert d['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
    assert any(x['medicine_index']==2 and x['code']=='INVALID_DOSE_FORMAT' for x in d['issues'])
