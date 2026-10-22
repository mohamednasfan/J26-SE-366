"""Clinical review service: source-gated, fail-closed, auditable warnings only."""
from __future__ import annotations
import os
from pathlib import Path
from medsafe.rule_registry import load_reviewed_rules, match_rule, assess_reviewed_rule, RuleRegistryError
from medsafe.extraction import number_and_unit, parse_frequency, parse_weight

def assess_report(report):
    """Optional exact-match, source-reviewed threshold assessment only."""
    # The default rules file belongs at the repository root, not backend/app.
    default_registry=Path(__file__).resolve().parents[3]/'reviewed_rules_EMPTY.json'
    path=Path(os.getenv('MEDSAFE_REVIEWED_RULES',str(default_registry)))
    registry_error=False
    try:
        rules=load_reviewed_rules(path)
    except (RuleRegistryError,ValueError,OSError):
        rules=[]
        registry_error=True
        report['issues'].append({
            'code':'REVIEWED_RULE_REGISTRY_UNAVAILABLE','severity':'BLOCK',
            'message':'Reviewed dose reference registry could not be validated; no dose or age clearance is possible.',
            'field':None
        })
    for index,m in enumerate(report.get('medications',[]),1):
        fields=m['extraction']['fields']
        # A clinical rule MUST have separately confirmed product + indication + age population.
        # These context fields are never silently inferred from patient demographics or OCR.
        rule=match_rule(rules,ingredient=fields.get('medicine',''),product_identifier=fields.get('product_identifier',''),
                        route=fields.get('route',''),indication=fields.get('indication',''),
                        population=fields.get('population','')) if rules else None
        # Never screen against a possibly contradictory or incomplete transcription.
        # Even a matching label must abstain when extraction has a blocking issue.
        blocked=bool(m['extraction'].get('candidate_only')) or any(
            item.get('severity')=='BLOCK' for item in m.get('issues',[])
        )
        if blocked:
            rule=None
        parsed=number_and_unit(fields.get('dose',''))
        freq=parse_frequency(fields.get('frequency',''))
        weight=parse_weight(fields.get('weight',''))
        if weight is not None and not 0<weight<=500:
            weight=None
        result=assess_reviewed_rule(rule,dose=parsed[0] if parsed else None,
                                    unit=parsed[1] if parsed else '',frequency=freq,
                                    weight_kg=weight)
        m['reviewed_dose_rule']=result
        m['dose_validation_available']=result['status']!='NOT_EVALUATED'
        age_text=fields.get('age','')
        from medsafe.extraction import parse_age
        age=parse_age(age_text)
        if age is not None and not 0<=age<=120:
            age=None
        age_check={'status':'UNABLE_TO_VALIDATE','reason':'No matched source-reviewed age interval and/or verified age'}
        if rule is not None and age is not None and type(rule.get('min_age_years')) in (int,float) and type(rule.get('max_age_years')) in (int,float):
            lo,hi=rule['min_age_years'],rule['max_age_years']
            if 0<=lo<=hi<=120:
                age_check={'status':'REVIEW_AGE_RANGE_FLAG' if not lo<=age<=hi else 'WITHIN_REVIEWED_AGE_RANGE_NOT_PROOF_OF_SAFETY',
                           'source_url':rule['source_url'],'min_age_years':lo,'max_age_years':hi,
                           'note':'Age-range screen only; not an individual clinical dosing recommendation'}
        if blocked:
            age_check={'status':'UNABLE_TO_VALIDATE',
                       'reason':'Prescription contains unresolved or conflicting fields; verify transcription first'}
            result={**result, 'reason':'Prescription contains unresolved or conflicting fields; verify transcription first'}
            m['reviewed_dose_rule']=result
            m['dose_validation_available']=False
        m['reviewed_age_rule']=age_check
        from medsafe.validation import finding
        alerts=[]
        if result['status']=='REVIEW_THRESHOLD_EXCEEDED':
            alerts.append(finding('REVIEWED_RULE_THRESHOLD_EXCEEDED','CAUTION',
                 'The confirmed amount or daily total exceeds a matching source-reviewed threshold; qualified clinician assessment is required. This is a screening flag, not an overdose diagnosis.','dose'))
        if result['status']=='REVIEW_THRESHOLD_EXCEEDED' and result.get('reviewed_adverse_effects'):
            effects='; '.join(result['reviewed_adverse_effects'])
            alerts.append(finding('REVIEWED_LABEL_ADVERSE_EFFECT_EVIDENCE','CAUTION',
                 'Source-reviewed overdose warning evidence: '+effects[:360]+'. This is not an individual side-effect prediction.', 'dose'))
        if age_check['status']=='REVIEW_AGE_RANGE_FLAG':
            alerts.append(finding('REVIEWED_AGE_RANGE_FLAG','CAUTION',
                 'Patient age falls outside a matching source-reviewed age range; qualified clinician review is required.','age'))
        for a in alerts:
            m['issues'].append(a)
            report['issues'].append(dict(a,medicine_index=index))
    report['reviewed_rule_count']=len(rules)
    report['reviewed_rule_registry_status']='INVALID_OR_UNAVAILABLE' if registry_error else ('APPROVED_RULES_LOADED' if rules else 'NO_APPROVED_RULES')
    report['rule_assessment_policy']='Exact reviewed product, indication, route, population, dose unit and verified weight where relevant. Below a threshold never means safe.'
    return report

