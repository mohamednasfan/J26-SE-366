"""Notebook 47: fail-closed full-page OCR software regression fixtures.

Synthetic strings test *program behavior*; they are not actual medical drug data
or proof that any TrOCR prediction is correct.
"""
import io
from PIL import Image
from medsafe.extraction import extract_prescription
from medsafe.pipeline import analyze_text
from medsafe.segments import propose_text_regions
from medsafe import ocr, trocr


def codes(result):
    return {x['code'] for x in result['issues']}


def test_two_unlabeled_drugs_are_separate_candidates_not_dosed():
    out=analyze_text('Tab. Amoxicillin 500 mg BD\nCap. Omeprazole 20 mg OD\nAge: 30',
                     ocr_mode=True,ocr_engine='trocr_notebook44_finetuned')
    assert out['medication_count']==2
    a,b=[v['extraction']['fields'] for v in out['medications']]
    assert (a['medicine'],a['strength'],a['frequency'])==('Amoxicillin','500 mg','BD')
    assert (b['medicine'],b['strength'],b['frequency'])==('Omeprazole','20 mg','OD')
    assert a['dose']==b['dose']==''
    assert 'MISSING_DOSE' in codes(out)
    assert 'OCR_CANDIDATE_NEEDS_CONFIRMATION' in codes(out)
    assert out['status']=='BLOCKED_INVALID_OR_INCOMPLETE'
    assert out['clinical_clearance'] is False


def test_unlabeled_rx_prefix_not_medicine_name():
    out=analyze_text('Rx: Tab. ExampleMed 250 mg BID\nAge: 42',ocr_mode=True)
    assert out['extraction']['fields']['medicine']=='ExampleMed'
    assert out['extraction']['fields']['strength']=='250 mg'
    assert out['extraction']['fields']['dose']==''


def test_syrup_ml_is_concentration_or_strength_not_administered_volume():
    out=analyze_text('Syrup ExampleMed 5 mL 1-0-1\nAge: 7',ocr_mode=True)
    assert out['extraction']['fields']['strength']=='5 mL'
    assert out['extraction']['fields']['frequency']=='twice daily'
    assert out['extraction']['fields']['dose']==''
    assert out['clinical_clearance'] is False


def test_fractional_handwritten_schedule_not_made_up():
    out=analyze_text('Tab. ExampleMed 200 mg 1/2-0-1/2',ocr_mode=True)
    assert out['extraction']['fields']['frequency']==''
    assert 'MISSING_FREQUENCY' in codes(out)


def test_noise_without_dosage_form_does_not_create_medicine_name():
    out=analyze_text('Maybe illegible 500mg BD\nNote on sheet',ocr_mode=True)
    assert out['extraction']['fields']['medicine']==''
    assert 'MISSING_MEDICINE' in codes(out)


def test_age_is_not_guessed_from_unlabeled_number():
    out=analyze_text('Tab. ExampleMed 500 mg BD\n37',ocr_mode=True)
    assert out['extraction']['fields']['age']==''
    assert 'MISSING_AGE' in codes(out)


def test_region_inference_length_mismatch_is_error(monkeypatch):
    from medsafe import segments
    monkeypatch.setattr(segments,'propose_text_regions',lambda im:([im,im],[{'x1':0,'y1':0,'x2':50,'y2':30}, {'x1':50,'y1':0,'x2':100,'y2':30}]))
    monkeypatch.setattr(trocr,'infer_regions',lambda regions:['OnlyOne'])
    b=io.BytesIO();Image.new('RGB',(160,80),'white').save(b,format='PNG')
    try:
        ocr.ocr_image(b.getvalue(),engine='trocr')
        assert False,'Should reject silently omitted text regions'
    except RuntimeError as e:
        assert 'different number' in str(e)


def test_merged_ink_proposals_are_review_only_and_bounded():
    from PIL import ImageDraw
    im=Image.new('RGB',(500,350),'white')
    d=ImageDraw.Draw(im)
    d.rectangle((20,95,470,315),outline='black',width=3)
    for y in range(110,300,30):
        d.line((30,y,440,y+8),fill='black',width=2)
    regions,boxes=propose_text_regions(im)
    assert len(regions)==len(boxes)
    assert all(0<=b['x1']<b['x2']<=im.width and 0<=b['y1']<b['y2']<=im.height for b in boxes)
    assert all(b['geometry_verified'] is False for b in boxes)
    assert all((b['y2']-b['y1'])<150 for b in boxes), 'Do not feed enormous multirow crops into word-level TrOCR'
