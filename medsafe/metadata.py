"""Strict, source-grounded prescription metadata extraction; no inferred identities."""
import re
from datetime import datetime

LABELS = {
    'hospital_name': r'(?:hospital|clinic|medical\s+centre|medical\s+center|institution)',
    'hospital_address': r'(?:hospital\s+address|clinic\s+address|facility\s+address)',
    'hospital_phone': r'(?:hospital\s+phone|clinic\s+phone|facility\s+phone)',
    'doctor_name': r'(?:doctor|dr\.?|physician|prescriber)',
    'doctor_registration': r'(?:registration\s*(?:no\.?|number)|(?:slmc|license|licence)\s*(?:no\.?|number)?)',
    'doctor_specialization': r'(?:speciali[sz]ation|specialty)',
    'patient_name': r'(?:patient(?:\s+name)?|pt\.?\s*name)',
    'patient_age': r'(?:patient\s+age|age)',
    'patient_dob': r'(?:date\s+of\s+birth|dob)',
    'patient_sex': r'(?:sex|gender)',
    'patient_weight': r'(?:patient\s+weight|weight)',
    'prescription_date': r'(?:prescription\s+date|rx\s+date|date)',
    'prescription_number': r'(?:prescription\s*(?:no\.?|number|id)|rx\s*(?:no\.?|number))',
    'diagnosis': r'(?:diagnosis|dx)',
    'allergies': r'(?:allergies|allergy)',
}
MED_FIELDS={'medicine','dose','dosage','strength','frequency','route','duration','quantity','instructions'}

def extract_metadata(text, *, ocr_mode=False):
    if not isinstance(text,str): raise ValueError('Text required')
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    values={key:None for key in LABELS}
    evidence={}
    conflicts=[]
    for line_number,line in enumerate(lines,1):
        for key, label in LABELS.items():
            m=re.fullmatch(r'\s*(?:'+label+r')\s*[:=\-]\s*(.{1,180})\s*',line,re.I)
            if not m: continue
            value=m.group(1).strip()
            if not value: continue
            if key=='prescription_date':
                valid=False
                for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d/%m/%y','%d-%m-%y'):
                    try: datetime.strptime(value,fmt);valid=True;break
                    except ValueError:pass
                if not valid: conflicts.append({'field':key,'issue':'UNRECOGNIZED_DATE_FORMAT','source_line':line_number});continue
            if values[key] is None:
                values[key]=value
                evidence[key]={'source_line':line_number,'source_text':line,'verification':'UNVERIFIED_OCR' if ocr_mode else 'TRANSCRIBED_NOT_INDEPENDENTLY_VERIFIED'}
            elif values[key].casefold()!=value.casefold():
                conflicts.append({'field':key,'issue':'CONFLICTING_VALUES','source_line':line_number})
            break
    return {'fields':values,'evidence':evidence,'conflicts':conflicts,'missing_fields':[k for k,v in values.items() if v is None], 'human_review_required':True, 'signature_authenticated':False}
