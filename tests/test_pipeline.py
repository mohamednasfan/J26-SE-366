import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from medsafe.api import app
from medsafe.pipeline import analyze_text, analyze_image
from medsafe.references import lookup


def evaluate(t):
    return analyze_text(t)


def codes(r):
    return {x['code'] for x in r['issues']}


def sample(med='DEMO-DRUG-A', dose='100 mg', frequency='twice daily', age='30 years', route='oral'):
    return f'Medicine: {med}\nDose: {dose}\nFrequency: {frequency}\nAge: {age}\nRoute: {route}'


def test_fixture_within_limit_not_clinically_clear():
    a=evaluate(sample())
    assert a['checks']['dose_safety']=='WITHIN_SYNTHETIC_FIXTURE_ONLY'
    assert a['status']=='REVIEW_REQUIRED'
    assert a['clinical_clearance'] is False
    assert a['can_auto_dispense'] is False


def test_fixture_overdose_and_age():
    a=evaluate(sample(dose='300 mg',age='10'))
    assert a['checks']['dose_safety']=='SYNTHETIC_LIMIT_EXCEEDED'
    assert a['checks']['age_appropriateness']=='SYNTHETIC_AGE_RULE_FLAG'
    assert {'SYNTHETIC_OVERDOSE_FLAG','SYNTHETIC_AGE_FLAG'} <= codes(a)
    assert a['status']=='ADVISORY_FLAGS'


def test_daily_total_exceeded_but_not_single():
    a=evaluate(sample(dose='200 mg',frequency='three times daily'))
    assert a['checks']['dose_safety']=='SYNTHETIC_LIMIT_EXCEEDED'


def test_unknown_drug_not_marked_safe():
    a=evaluate(sample(med='Amoxicillin'))
    assert a['checks']['dose_safety']=='NO_VERIFIED_DRUG_SPECIFIC_RULE'
    assert a['checks']['age_appropriateness']=='NO_VERIFIED_AGE_SPECIFIC_RULE'
    assert 'UNVERIFIED_DRUG_RULE' in codes(a)
    assert a['clinical_clearance'] is False


def test_invalid_dose_and_missing_age_blocks():
    a=evaluate('Medicine: DrugAlpha\nDose: -500 mg\nFrequency: bid')
    assert a['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
    assert {'INVALID_DOSE_FORMAT', 'MISSING_AGE'} <= codes(a)


def test_invalid_age_and_frequency():
    a=evaluate(sample(frequency='PRN',age='-5 years'))
    assert {'INVALID_AGE', 'INVALID_FREQUENCY'} <= codes(a)
    assert a['checks']['dose_safety']=='NOT_EVALUATED'


def test_no_inf_numeric_and_no_guess_for_ml():
    a=evaluate(sample(dose='999999999 mg'))
    assert 'INVALID_DOSE_VALUE' in codes(a)
    b=evaluate(sample(dose='5 mL'))
    assert b['checks']['dose_safety']=='CANNOT_VERIFY_CONCENTRATION'
    assert 'UNIT_CONVERSION_UNSUPPORTED' in codes(b)


def test_multi_medicine_no_auto_pick():
    a=evaluate('Medicine: DEMO-DRUG-A\nMedicine: AnotherDrug\nDose: 100 mg\nFrequency: BID\nAge: 20')
    assert a['medication_count'] == 2
    assert 'MISSING_DOSE' in codes(a)
    assert 'MULTIPLE_MEDICATIONS_INTERACTION_UNVERIFIED' in codes(a)
    assert a['status']=='BLOCKED_INVALID_OR_INCOMPLETE'


def test_ocr_uncertainty_blocks_even_demo():
    a=analyze_text(sample(),ocr_confidence=.6,ocr_mode=True)
    assert a['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
    assert a['checks']['dose_safety']=='NOT_EVALUATED'


def test_unsupported_drug_chars():
    a=evaluate(sample(med='???'))
    assert 'INVALID_MEDICINE_FORMAT' in codes(a)


def test_unit_conversion_precise():
    assert evaluate(sample(dose='0.2 g'))['checks']['dose_safety']=='WITHIN_SYNTHETIC_FIXTURE_ONLY'
    assert evaluate(sample(dose='300000 mcg'))['checks']['dose_safety']=='SYNTHETIC_LIMIT_EXCEEDED'


def test_reference_404_returns_unverified():
    class Resp:
        status_code=404
    class Stub:
        def get(self,*a,**kw): return Resp()
    result=lookup('unrealdrug',session=Stub())
    assert result['status']=='NO_EXACT_MATCH_FOUND'
    assert result['dose_threshold_extracted'] is False


def test_reference_failure_returns_unavailable():
    import requests
    class Stub:
        def get(self,*a,**kw): raise requests.Timeout()
    assert lookup('Amoxicillin',session=Stub())['status']=='REFERENCE_UNAVAILABLE'


def test_reference_candidate_not_verified():
    class Resp:
        status_code=200
        def __init__(self,p): self.p=p
        def raise_for_status(self):pass
        def json(self):return self.p
    class Stub:
        def get(self,url,**kw):
            if 'dailymed' in url:
                return Resp({'data':[{'title':'AMOXICILLIN TABLET','setid':'example-set-id-12345'}, {'title':'AMPICILLIN TABLET','setid':'fake-set-id-12345'}]})
            return Resp({'results':[{'openfda':{'generic_name':['AMOXICILLIN']},'set_id':'example-set-id-12345'}]})
    r=lookup('Amoxicillin',session=Stub())
    assert r['status']=='CANDIDATES_FOUND'
    assert len(r['dailymed']) == 1 and len(r['openfda'])==1
    assert r['dose_threshold_extracted'] is False


def test_api_health_and_text():
    with TestClient(app) as c:
        assert c.get('/api/health').json()['model_trained'] is False
        assert c.get('/').status_code==200
        r=c.post('/api/analyze-text',json={'text':sample()})
        assert r.status_code==200 and r.json()['checks']['medicine_identity']=='SYNTHETIC_FIXTURE_ONLY'


def test_api_rejects_fake_image_and_oversized():
    with TestClient(app) as c:
        assert c.post('/api/analyze-image',content=b'hello',headers={'content-type':'image/png'}).status_code==422
        assert c.post('/api/analyze-image',content=b'X',headers={'content-type':'text/plain'}).status_code==415
        assert c.post('/api/analyze-image',content=b'x'*(8*1024*1024+1),headers={'content-type':'image/png'}).status_code==413


def test_real_tesseract_image_endpoint():
    # Proves OCR executable integration on generated, non-sensitive research text.
    im=Image.new('RGB',(1000,310),'white'); d=ImageDraw.Draw(im)
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    f=ImageFont.truetype(font_path,30) if Path(font_path).exists() else ImageFont.load_default()
    for idx,line in enumerate(['Medicine: DEMO-DRUG-A','Dose: 100 mg','Frequency: twice daily','Age: 30 years','Route: oral']):
        d.text((28,10+idx*57),line,fill='black',font=f)
    b=io.BytesIO();im.save(b,format='PNG')
    with TestClient(app) as c:
        r=c.post('/api/analyze-image',content=b.getvalue(),headers={'content-type':'image/png'})
        assert r.status_code==200
        j=r.json()
        assert j['ocr']['engine']=='tesseract'
        assert j['input_method']=='IMAGE_OCR'
        assert j['clinical_clearance'] is False
        assert j['extraction']['fields']['age'].lower().startswith('30')
