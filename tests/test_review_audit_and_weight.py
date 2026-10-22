import io
import json
from PIL import Image
from fastapi.testclient import TestClient
from medsafe.rule_registry import assess_reviewed_rule

def test_weighted_threshold_rejects_missing_weight_and_warns_with_evidence():
    rule={'review_status':'APPROVED_BY_QUALIFIED_REVIEWER',
          'dose_unit':'mg','max_single':100,'max_daily':200,
          'max_single_mg_per_kg':2,'max_daily_mg_per_kg':4,
          'source_url':'https://example.org/synthetic','reviewer':'test-only',
          'version':'1','source_section':'simulation',
          'overdose_adverse_effects':['synthetic mock label warning']}
    missing=assess_reviewed_rule(rule,dose=30,unit='mg',frequency=2)
    assert missing['status']=='NOT_EVALUATED'
    flagged=assess_reviewed_rule(rule,dose=30,unit='mg',frequency=2,weight_kg=10)
    assert flagged['status']=='REVIEW_THRESHOLD_EXCEEDED'
    assert flagged['reviewed_max_single']==20
    assert flagged['reviewed_adverse_effects']==['synthetic mock label warning']
    assert flagged['clinical_clearance'] is False

def test_prescription_review_revision_audit(monkeypatch,tmp_path):
    import medsafe.storage as storage
    import medsafe.api_product as product
    monkeypatch.setattr(storage,'DATA',tmp_path)
    monkeypatch.setattr(product,'recognize',lambda data,engine:{
        'text':'Medicine: FakeA\nDose: 2 mg\nAge: 20 years\nFrequency: daily',
        'engine':engine,'confidence':None,'regions':[],'warnings':['STUB']})
    image=Image.new('RGB',(100,50),'white')
    stream=io.BytesIO();image.save(stream,'PNG')
    with TestClient(product.app) as client:
        submitted=client.post('/api/prescriptions?engine=tesseract',
            files={'file':('test.png',stream.getvalue(),'image/png')})
        assert submitted.status_code==200,submitted.text
        pid=submitted.json()['id']
        before=client.get('/api/prescriptions/'+pid+'/audit').json()['events']
        assert len(before)==1 and before[0]['action']=='OCR_CREATED_UNVERIFIED'
        for med in ('FakeA','FakeB'):
            response=client.post('/api/prescriptions/'+pid+'/review',json={
                'corrected_text':f'Medicine: {med}\nAge: 20 years\nDose: 2 mg\nFrequency: daily',
                'reviewer_confirmed':True})
            assert response.status_code==200,response.text
            assert response.json()['report']['clinical_clearance'] is False
        events=client.get('/api/prescriptions/'+pid+'/audit').json()['events']
        assert [event['action'] for event in events]==[
            'TRANSCRIPTION_REVISED','TRANSCRIPTION_CONFIRMED','OCR_CREATED_UNVERIFIED']
        assert events[0]['before_sha256']!=events[0]['after_sha256']
        assert client.delete('/api/prescriptions/'+pid).status_code==200
        assert client.get('/api/prescriptions/'+pid+'/audit').status_code==404

def test_research_endpoint_omits_raw_predictions(monkeypatch,tmp_path):
    from backend.app.api.routes.research_results import benchmark_results,historical_baseline
    path=tmp_path/'benchmark.json'
    path.write_text(json.dumps({'schema':'medsafe.ocr_benchmark.v1',
      'label_policy':'HUMAN_VERIFIED_TEST_ONLY','dataset_size':1,
      'engines':{'tesseract':{'thesis_eligible':True,'n_total':1,'n_succeeded':1,
      'coverage':1,'metrics':{'ocr':{'CER':.05}},'predictions':[{'transcription':'CONFIDENTIAL'}]}}}))
    monkeypatch.setenv('MEDSAFE_BENCHMARK_RESULTS',str(path))
    report=benchmark_results()
    assert report['status']=='HUMAN_VERIFIED_TEST'
    assert 'predictions' not in report['engines']['tesseract']
    assert 'CONFIDENTIAL' not in json.dumps(report)
    archived=historical_baseline()
    assert archived['n_aligned_images']==780
