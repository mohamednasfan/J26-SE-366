"""Single API to join OCR, structured extraction, validation and reference evidence."""
from __future__ import annotations
from .extraction import extract_prescription
from .validation import validate, finding
from .references import lookup
from .metadata import extract_metadata


def analyze_text(text: str, *, ocr_confidence=None, ocr_mode=False,
                 ocr_engine=None, with_references=False, session=None):
    if not isinstance(text,str) or len(text)>12000:
        raise ValueError('Input text must be a string no longer than 12,000 characters.')
    metadata=extract_metadata(text,ocr_mode=ocr_mode)
    parsed=extract_prescription(text,allow_unlabeled=ocr_mode)
    medication_results=[]
    for block in parsed:
        outcome=validate(block['fields'], conflicting_fields=block['conflicting_fields'],
                         duplicate_fields=block['duplicate_fields'],
                         ocr_confidence=ocr_confidence,ocr_mode=ocr_mode)
        outcome['extraction']=block
        if ocr_mode and block.get('candidate_only'):
            outcome['issues'].append(finding('OCR_CANDIDATE_NEEDS_CONFIRMATION','BLOCK',
                'Unlabeled OCR medicine evidence requires human confirmation before dosing decisions.','medicine'))
            outcome['status']='BLOCKED_INVALID_OR_INCOMPLETE'
        med=block['fields']['medicine']
        blocked_med=any(x['severity']=='BLOCK' and (
            x['field'] in ('medicine','ocr') or x['code']=='CONFLICTING_FIELDS') for x in outcome['issues'])
        if with_references and med and not blocked_med and not block.get('candidate_only') and med.lower()!='demo-drug-a':
            outcome['references']=lookup(med,session=session)
        else:
            outcome['references']={'status':'NOT_QUERIED',
                'note':'Lookup disabled, synthetic fixture, or uncertain medicine identity.'}
        if with_references and outcome['references']['status'] in ('NO_EXACT_MATCH_FOUND','REFERENCE_UNAVAILABLE'):
            outcome['issues'].append(finding('DRUG_IDENTITY_NOT_CONFIRMED','CAUTION',
                 'No confirmatory label evidence. Absence from this search is not proof of an invalid drug.','medicine'))
        medication_results.append(outcome)

    main=medication_results[0]
    # Top-level consumers must see errors from EVERY medicine, not only first.
    main['issues']=[dict(issue,medicine_index=i+1)
                    for i,medication in enumerate(medication_results)
                    for issue in medication['issues']]
    main['medications']=[{'medicine_index':i+1,'extraction':r['extraction'],
                         'status':r['status'],'issues':r['issues'],
                         'checks':r['checks'],'references':r['references']}
                        for i,r in enumerate(medication_results)]
    main['medication_count']=len(parsed)
    main['input_method']='IMAGE_OCR' if ocr_mode else 'DIRECT_TRANSCRIPT'
    main['ocr']={'engine':ocr_engine or 'unknown','confidence':ocr_confidence,
                 'confidence_is_calibrated':False} if ocr_mode else None
    # Detect duplicate drug entries that might hide contradictory regimens.
    names=[str(r['extraction']['fields']['medicine']).strip().casefold() for r in medication_results]
    duplicates={n for n in names if n and names.count(n)>1}
    if duplicates:
        main['issues'].append(finding('DUPLICATE_MEDICATION_REGIMEN','BLOCK',
             'The same medicine appears in multiple blocks; verify potential contradictory doses.','medicine'))
    if len(parsed)>1:
        main['issues'].append(finding('MULTIPLE_MEDICATIONS_INTERACTION_UNVERIFIED','CAUTION',
                 'Drug-drug interactions and cumulative dosing across medications are not evaluated.'))
    if duplicates or any(r['status']=='BLOCKED_INVALID_OR_INCOMPLETE' for r in medication_results):
        main['status']='BLOCKED_INVALID_OR_INCOMPLETE'
    elif any(r['status']=='ADVISORY_FLAGS' for r in medication_results):
        main['status']='ADVISORY_FLAGS'
    else:
        main['status']='REVIEW_REQUIRED'
    main['prescription_details']=metadata
    if metadata['conflicts']:
        main['issues'].append(finding('CONFLICTING_PRESCRIPTION_DETAILS','BLOCK',
            'Conflicting prescription metadata requires manual review.'))
        main['status']='BLOCKED_INVALID_OR_INCOMPLETE'
    main['clinical_clearance']=False
    main['can_auto_dispense']=False
    main['requires_professional_review']=True
    return main


def analyze_image(data: bytes, *, engine='auto', with_references=False, session=None):
    from .ocr import ocr_image
    ocr=ocr_image(data,engine=engine)
    result=analyze_text(ocr['text'],ocr_confidence=ocr['confidence'],ocr_mode=True,
                        ocr_engine=ocr['engine'],with_references=with_references,session=session)
    result['ocr'].update({key:value for key,value in ocr.items()
                          if key not in ('text','confidence','engine')})
    # Client-only ephemeral transcript for correction; never saved on server or forwarded to references.
    result['transcription_for_review']=ocr['text']
    return result
