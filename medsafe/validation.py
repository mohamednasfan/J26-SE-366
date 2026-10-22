"""Explicit invalid-field detection and closed-world synthetic dose-rule checks.

No real drug is automatically declared safe or overdosed from label snippets.
"""
from __future__ import annotations
import math
import re
from .extraction import number_and_unit, parse_age, parse_frequency, parse_weight

# FICTITIOUS drug for tests/UI demonstration ONLY. These thresholds are not medical facts.
DEMO_RULES = {
    'demo-drug-a': {'source_kind': 'SYNTHETIC_TEST_FIXTURE', 'source_id': 'SYNTH-001',
                    'min_age_years': 12, 'max_age_years': 120,
                    'dose_unit': 'mg', 'max_single_mg': 250.0, 'max_daily_mg': 500.0,
                    'route': 'oral', 'rule_version': '1'}
}


def finding(code, severity, message, field=None):
    return {'code': code, 'severity': severity, 'message': message, 'field': field}


def validate(fields: dict, *, conflicting_fields=(), duplicate_fields=(), ocr_confidence=None, ocr_mode=False):
    problems = []
    med = str(fields.get('medicine') or '').strip()
    dose_text = str(fields.get('dose') or '').strip()
    freq_text = str(fields.get('frequency') or '').strip()
    age_text = str(fields.get('age') or '').strip()
    route = str(fields.get('route') or '').strip().lower()
    weight_text = str(fields.get('weight') or '').strip()

    for f in conflicting_fields:
        problems.append(finding('CONFLICTING_FIELDS', 'BLOCK', f'Conflicting {f} entries; cannot choose automatically.', f))
    for f in duplicate_fields:
        if f not in conflicting_fields:
            problems.append(finding('DUPLICATE_FIELD', 'BLOCK', f'Multiple {f} entries found; single-medication input required.', f))
    if not med:
        problems.append(finding('MISSING_MEDICINE', 'BLOCK', 'Medicine name not found.', 'medicine'))
    elif not re.fullmatch(r'[A-Za-z][A-Za-z0-9 -]{1,79}', med):
        problems.append(finding('INVALID_MEDICINE_FORMAT', 'BLOCK', 'Medicine name contains unsupported characters or length.', 'medicine'))
    if not dose_text:
        problems.append(finding('MISSING_DOSE', 'BLOCK', 'Dose is missing.', 'dose'))
    dose = number_and_unit(dose_text) if dose_text else None
    if dose_text and not dose:
        problems.append(finding('INVALID_DOSE_FORMAT', 'BLOCK', 'Use a positive dose with a recognized unit (mg, g, mcg or mL).', 'dose'))
    elif dose and (not math.isfinite(dose[0]) or dose[0] <= 0 or (dose[0] * (1000 if dose[1]=='g' else 0.001 if dose[1]=='mcg' else 1)) > 100000):
        problems.append(finding('INVALID_DOSE_VALUE', 'BLOCK', 'Dose must be a realistic positive finite number; requires review.', 'dose'))
    if not freq_text:
        problems.append(finding('MISSING_FREQUENCY', 'BLOCK', 'Frequency is missing; cannot calculate a daily total.', 'frequency'))
    freq = parse_frequency(freq_text) if freq_text else None
    if freq_text and freq is None:
        problems.append(finding('INVALID_FREQUENCY', 'BLOCK', 'Frequency ambiguous or unsupported (including PRN).', 'frequency'))
    if not age_text:
        problems.append(finding('MISSING_AGE', 'BLOCK', 'Patient age missing; age validation unavailable.', 'age'))
    age = parse_age(age_text) if age_text else None
    if age_text and (age is None or not 0 <= age <= 120):
        problems.append(finding('INVALID_AGE', 'BLOCK', 'Age must be between 0 and 120 years.', 'age'))
    if weight_text and (parse_weight(weight_text) is None or not 0 < parse_weight(weight_text) <= 500):
        problems.append(finding('INVALID_WEIGHT', 'BLOCK', 'Weight must be a positive number in kg.', 'weight'))
    if route and route not in ('oral', 'po', 'topical', 'iv', 'im', 'subcutaneous', 'inhaled', 'rectal', 'ophthalmic'):
        problems.append(finding('UNSUPPORTED_ROUTE', 'BLOCK', 'Route cannot be parsed safely.', 'route'))
    if ocr_mode and (ocr_confidence is None or ocr_confidence < 0.85):
        problems.append(finding('LOW_OCR_CONFIDENCE', 'BLOCK', 'OCR evidence is uncertain; verify transcription before dose checks.', 'ocr'))

    critical = any(p['severity'] == 'BLOCK' for p in problems)
    # Synthetic rule can only be exercised for explicit demo medication; never clinical.
    demo_rule = DEMO_RULES.get(med.lower())
    evaluations = {'medicine_identity': 'UNVERIFIED', 'dose_safety': 'NOT_EVALUATED',
                   'age_appropriateness': 'NOT_EVALUATED', 'research_rule_source': None}
    if demo_rule:
        evaluations['research_rule_source'] = demo_rule['source_id']
    if not critical and dose and freq is not None and age is not None:
        if demo_rule:
            evaluations['medicine_identity'] = 'SYNTHETIC_FIXTURE_ONLY'
            if not route or route not in (demo_rule['route'], 'po' if demo_rule['route']=='oral' else demo_rule['route']):
                problems.append(finding('DEMO_ROUTE_MISMATCH', 'CAUTION', 'Synthetic rule requires an explicit matching route.', 'route'))
                evaluations['dose_safety'] = 'CANNOT_VERIFY_ROUTE'
            else:
                if dose[1] == 'mg':
                    mg = dose[0]
                elif dose[1] == 'g':
                    mg = dose[0] * 1000
                elif dose[1] == 'mcg':
                    mg = dose[0] / 1000
                else:
                    mg = None
                if mg is None:
                    problems.append(finding('UNIT_CONVERSION_UNSUPPORTED', 'CAUTION', 'mL needs verified product concentration.', 'dose'))
                    evaluations['dose_safety'] = 'CANNOT_VERIFY_CONCENTRATION'
                elif mg > demo_rule['max_single_mg'] or mg*freq > demo_rule['max_daily_mg']:
                    evaluations['dose_safety'] = 'SYNTHETIC_LIMIT_EXCEEDED'
                    problems.append(finding('SYNTHETIC_OVERDOSE_FLAG', 'CAUTION', 'Dose exceeds the fictitious research fixture threshold. Not a clinical overdose determination.', 'dose'))
                else:
                    evaluations['dose_safety'] = 'WITHIN_SYNTHETIC_FIXTURE_ONLY'
            if age < demo_rule['min_age_years'] or age > demo_rule['max_age_years']:
                evaluations['age_appropriateness'] = 'SYNTHETIC_AGE_RULE_FLAG'
                problems.append(finding('SYNTHETIC_AGE_FLAG', 'CAUTION', 'Age is outside this fictitious research fixture age band.', 'age'))
            else:
                evaluations['age_appropriateness'] = 'WITHIN_SYNTHETIC_FIXTURE_ONLY'
        else:
            evaluations['dose_safety'] = 'NO_VERIFIED_DRUG_SPECIFIC_RULE'
            evaluations['age_appropriateness'] = 'NO_VERIFIED_AGE_SPECIFIC_RULE'
            problems.append(finding('UNVERIFIED_DRUG_RULE', 'CAUTION', 'No reviewed, product/route-specific dosing threshold exists in this installation.', 'medicine'))
    status = 'BLOCKED_INVALID_OR_INCOMPLETE' if critical else ('ADVISORY_FLAGS' if any(p['severity']=='CAUTION' and p['code']!='UNVERIFIED_DRUG_RULE' for p in problems) else 'REVIEW_REQUIRED')
    return {'status': status, 'issues': problems, 'checks': evaluations,
            'clinical_clearance': False, 'can_auto_dispense': False,
            'requires_professional_review': True}
