"""Conservative prescription field extraction. No inference from missing fields."""
from __future__ import annotations
import re
from typing import Any

_MED = re.compile(r'^(?:medicine|medication|drug|name)\s*[:=-]\s*(.*?)\s*$', re.I)
_DOSE = re.compile(r'^(?:dose|dosage|amount)\s*[:=-]\s*(.*?)\s*$', re.I)
_FREQ = re.compile(r'^(?:frequency|freq|schedule)\s*[:=-]\s*(.*?)\s*$', re.I)
_AGE = re.compile(r'^(?:patient\s*age|age)\s*[:=-]\s*(.*?)\s*$', re.I)
_ROUTE = re.compile(r'^(?:route)\s*[:=-]\s*(.*?)\s*$', re.I)
_PRODUCT_IDENTIFIER = re.compile(r'^(?:product\s*(?:identifier|id)|verified\s*product)\s*[:=-]\s*(.*?)\s*$', re.I)
_INDICATION = re.compile(r'^(?:indication|verified\s*indication)\s*[:=-]\s*(.*?)\s*$', re.I)
_POPULATION = re.compile(r'^(?:population|verified\s*population)\s*[:=-]\s*(.*?)\s*$', re.I)
_STRENGTH = re.compile(r'^(?:strength|product\s*strength)\s*[:=-]\s*(.*?)\s*$', re.I)
_WEIGHT = re.compile(r'^(?:weight|patient\s*weight)\s*[:=-]\s*(.*?)\s*$', re.I)
_DOSE_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g|ml|mL)\s*$', re.I)
_AGE_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|y)?\s*$', re.I)
_WEIGHT_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*kg\s*$', re.I)
_FREQUENCIES = {'once daily': 1, 'daily': 1, 'once a day': 1, 'od': 1,
                'twice daily': 2, 'twice a day': 2, 'bid': 2,
                'three times daily': 3, 'three times a day': 3, 'tid': 3,
                'four times daily': 4, 'four times a day': 4, 'qid': 4,
                'bd': 2, 'tds': 3, 'qd': 1}
_ROUTES = {'oral', 'po', 'topical', 'iv', 'im', 'subcutaneous', 'inhaled', 'rectal', 'ophthalmic'}


def extract(text: str) -> dict[str, Any]:
    """Return extracted raw strings and parse-uncertainty flags, not guesses."""
    fields = {'medicine': '', 'dose': '', 'frequency': '', 'age': '', 'route': '', 'weight': '', 'strength': '', 'product_identifier': '', 'indication': '', 'population': ''}
    occurrences: dict[str, list[str]] = {k: [] for k in fields}
    patterns = {'medicine': _MED, 'dose': _DOSE, 'frequency': _FREQ,
                'age': _AGE, 'route': _ROUTE, 'weight': _WEIGHT, 'strength': _STRENGTH, 'product_identifier': _PRODUCT_IDENTIFIER, 'indication': _INDICATION, 'population': _POPULATION}
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    for line in nonempty:
        for key, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                occurrences[key].append(match.group(1).strip())
                break
    for key in fields:
        if occurrences[key]:
            fields[key] = occurrences[key][0]
    # Limited unlabeled-line fallback for a single explicit 'DrugName 250 mg BID'.
    if not fields['medicine'] and len(nonempty) == 1:
        m = re.fullmatch(r'([A-Za-z][A-Za-z\- ]{1,50})\s+(\d+(?:\.\d+)?)\s*(mg|mcg|g)\s+(once daily|twice daily|three times daily|daily|bid|tid|qid)', nonempty[0], re.I)
        if m:
            fields.update(medicine=m.group(1).strip(), dose=f'{m.group(2)} {m.group(3)}', frequency=m.group(4))
    conflicts = [key for key, values in occurrences.items() if len(set(x.casefold() for x in values)) > 1]
    return {'fields': fields, 'conflicting_fields': conflicts,
            'medicine_line_count': len(occurrences['medicine']), 'duplicate_fields': [key for key, values in occurrences.items() if len(values)>1], 'line_count': len(nonempty)}


def number_and_unit(value: str):
    m = _DOSE_PATTERN.fullmatch(value)
    return (float(m.group(1)), m.group(2).lower().replace('µg', 'mcg').replace('ug', 'mcg')) if m else None


def parse_age(value: str):
    m = _AGE_PATTERN.fullmatch(value)
    return float(m.group(1)) if m else None


def parse_weight(value: str):
    m = _WEIGHT_PATTERN.fullmatch(value)
    return float(m.group(1)) if m else None


def parse_frequency(value: str):
    normalized = re.sub(r'\s+', ' ', value.strip().lower())
    if normalized in _FREQUENCIES:
        return _FREQUENCIES[normalized]
    if re.fullmatch(r'[1-4]\s*(?:/\s*day|times\s*(?:a|per)\s*day)', normalized):
        return int(normalized[0])
    if re.fullmatch(r'(?:every|q)\s*(6|8|12|24)\s*(?:h|hr|hrs|hours?)', normalized):
        hours = int(re.search(r'(6|8|12|24)', normalized).group(1))
        return 24 // hours
    return None


def extract_prescription(text: str, *, allow_unlabeled: bool = False) -> list[dict[str, Any]]:
    """Extract one or more *explicitly labeled* medication blocks.

    Age and weight are patient-level context. An unlabeled drug list is not
    assumed to contain safe medication entities, since that would silently
    assign doses to the wrong medication.
    """
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    markers=[i for i,line in enumerate(lines) if _MED.match(line)]
    if allow_unlabeled and not markers:
        return extract_unlabeled_candidates(text)
    if len(markers)<=1:
        return [extract(text)]
    shared=[line for line in lines if _AGE.match(line) or _WEIGHT.match(line)]
    prefix=[line for line in lines[:markers[0]] if not (_AGE.match(line) or _WEIGHT.match(line))]
    results=[]
    for idx,start in enumerate(markers):
        stop=markers[idx+1] if idx+1<len(markers) else len(lines)
        body=[line for line in lines[start:stop] if not (_AGE.match(line) or _WEIGHT.match(line))]
        if idx==0:body=prefix+body
        results.append(extract('\n'.join(body+shared)))
    return results


# Handwriting often lacks "Medicine:" labels. The following *candidate-only*
# extraction requires a prescription-form marker AND a medicine-like token.
# Strength is NEVER treated as administered dose; OCR does not establish identity.
_UNLABELED_RX = re.compile(
    r"^\s*(?:(?:rx\s*[:.]?\s*)?)(?:tab(?:let)?|cap(?:sule)?|syr(?:up)?|inj(?:ection)?|drops?)\.?\s*[:.-]?\s*"
    r"(?P<med>[A-Za-z][A-Za-z0-9-]{1,49}(?:\s+[A-Za-z][A-Za-z0-9-]{1,30}){0,2})"
    r"(?P<tail>.*)$",re.I)
_UNLABELED_STRENGTH = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g|mL|ml)(?!\w)",re.I)
_UNLABELED_FREQ = re.compile(r"(?<!\w)(OD|QD|BD|BID|TDS|TID|QID)(?!\w)|\b(once|twice|three times|four times)\s+daily\b",re.I)
_UNLABELED_AGE = re.compile(r"\b(?:patient\s*)?age\s*[:=]?\s*(\d{1,3})(?:\s*(?:years?|yrs?))?\b",re.I)
_UNLABELED_SCHEDULE = re.compile(r"(?<![\d.])([01])\s*[-–]\s*([01])\s*[-–]\s*([01])(?!\d)")


def extract_unlabeled_candidates(text: str) -> list[dict[str, Any]]:
    """Return cautious per-line medicine candidates without invented doses.

    A line without a plausible dosage form marker does not produce a guessed
    medicine name. Unsupported or ambiguous schedules are left unresolved.
    """
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    shared=[]
    for line in lines:
        a=_UNLABELED_AGE.search(line)
        if a:shared.append('Age: '+a.group(1))
    results=[]
    for index,line in enumerate(lines):
        m=_UNLABELED_RX.match(line)
        if not m:
            continue
        tail=m.group('tail')
        # Parse medicine before a strength/frequency token when the OCR happens
        # to merge the medicine and those fields into a single line.
        med=m.group('med').strip()
        st=_UNLABELED_STRENGTH.findall(line)
        freq=_UNLABELED_FREQ.findall(tail)
        fval=''
        if len(freq)==1:
            fval=next((v for v in freq[0] if v),'')
        schedules=_UNLABELED_SCHEDULE.findall(tail)
        if len(schedules)==1 and not freq:
            fval={1:'once daily',2:'twice daily',3:'three times daily'}.get(sum(map(int,schedules[0])),'')
        # A dose strength is not the *prescribed administered dose*.
        evidence=[f'Medicine: {med}']
        if len(st)==1:
            evidence.append('Strength: '+st[0][0]+' '+st[0][1])
        if fval:
            evidence.append('Frequency: '+fval)
        evidence.extend(shared)
        extracted=extract('\n'.join(evidence))
        extracted['source_line_index']=index
        extracted['source_type']='UNLABELED_OCR_PRESCRIPTION_CANDIDATE'
        extracted['candidate_only']=True
        extracted['candidate_flags']=['OCR_MEDICINE_IDENTITY_UNVERIFIED',
                                      'PRESCRIBED_DOSE_NOT_ESTABLISHED']
        if len(st)>1:
            extracted['candidate_flags'].append('AMBIGUOUS_STRENGTH_MENTIONS')
        if len(freq)>1 or len(schedules)>1 or (freq and schedules):
            extracted['candidate_flags'].append('AMBIGUOUS_FREQUENCY_MENTIONS')
        results.append(extracted)
    if results:
        return results
    fallback=extract(text)
    fallback['source_type']='UNSTRUCTURED_OCR_NO_VALID_MEDICINE_CANDIDATES'
    fallback['candidate_only']=True
    fallback['candidate_flags']=['OCR_EXTRACTION_UNRESOLVED']
    return [fallback]
