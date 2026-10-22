"""Reviewed, source-specific medication thresholds; fail closed on incomplete evidence.

This registry intentionally ships with NO real-drug rules. Loading an entry
never implies that the product has undergone external clinical validation.
"""
from __future__ import annotations
from datetime import date
import json
import math
from pathlib import Path
from urllib.parse import urlparse

REQUIRED = (
    'ingredient', 'product_identifier', 'route', 'indication', 'population',
    'dose_unit', 'max_single', 'max_daily', 'source_url',
    'source_section', 'reviewer', 'review_date', 'version'
)
CONTEXT_KEYS = ('ingredient','product_identifier','route','indication','population')

class RuleRegistryError(ValueError):
    """A reviewed-rule file is malformed or inadequately documented."""

def _positive_finite_number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0

def _date(value, label):
    try:return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RuleRegistryError('Invalid '+label) from exc

def load_reviewed_rules(path: str | Path):
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise RuleRegistryError('Invalid registry JSON') from exc
    if not isinstance(data,list):
        raise RuleRegistryError('Rule registry must be a JSON list')
    result=[]
    seen=set()
    for i,entry in enumerate(data):
        if not isinstance(entry,dict):
            raise RuleRegistryError(f'Rule {i} is not an object')
        for key in REQUIRED:
            value=entry.get(key)
            if key in ('max_single','max_daily'):
                if not _positive_finite_number(value):
                    raise RuleRegistryError(f'Rule {i} invalid {key}')
            elif not isinstance(value,str) or not value.strip():
                raise RuleRegistryError(f'Rule {i} missing {key}')
        if entry.get('review_status')!='APPROVED_BY_QUALIFIED_REVIEWER':
            raise RuleRegistryError(f'Rule {i} is not approved by a qualified reviewer')
        if entry['dose_unit'] not in ('mg','mcg','g'):
            raise RuleRegistryError(f'Rule {i} invalid dose unit')
        try:url=urlparse(entry['source_url'])
        except ValueError as exc:raise RuleRegistryError(f'Rule {i} invalid source URL') from exc
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise RuleRegistryError(f'Rule {i} invalid HTTPS evidence URL')
        reviewed=_date(entry['review_date'],f'rule {i} review date')
        if reviewed>date.today():
            raise RuleRegistryError(f'Rule {i} review date is in the future')
        if 'expires_on' in entry:
            expiry=_date(entry['expires_on'],f'rule {i} expiry')
            if expiry<date.today():
                raise RuleRegistryError(f'Rule {i} expired')
            if expiry<reviewed:
                raise RuleRegistryError(f'Rule {i} expires before its review')
        lo,hi=entry.get('min_age_years'),entry.get('max_age_years')
        if lo is not None or hi is not None:
            if (type(lo) not in (int,float) or type(hi) not in (int,float) or
                not math.isfinite(lo) or not math.isfinite(hi) or not 0<=lo<=hi<=120):
                raise RuleRegistryError(f'Rule {i} invalid age interval')
        single_kg=entry.get('max_single_mg_per_kg')
        daily_kg=entry.get('max_daily_mg_per_kg')
        if single_kg is not None or daily_kg is not None:
            if (entry['dose_unit']!='mg' or
                not _positive_finite_number(single_kg) or
                not _positive_finite_number(daily_kg)):
                raise RuleRegistryError(f'Rule {i} invalid mg/kg dosing context')
        effects=entry.get('overdose_adverse_effects',[])
        if (not isinstance(effects,list) or any(
            not isinstance(v,str) or not v.strip() or len(v)>200 for v in effects
        ) or (effects and not str(entry.get('overdose_warning_source_section') or '').strip())):
            raise RuleRegistryError(f'Rule {i} has unsourced or invalid adverse-effect text')
        key=tuple(entry[k].casefold().strip() for k in CONTEXT_KEYS)
        if key in seen:
            raise RuleRegistryError(f'Rule {i} duplicates an existing context')
        seen.add(key)
        result.append(entry)
    return result

def match_rule(rules, *, ingredient, product_identifier, route, indication, population):
    target=(ingredient,product_identifier,route,indication,population)
    if not all(isinstance(v,str) and v.strip() for v in target):
        return None
    normalized=tuple(v.casefold().strip() for v in target)
    matches=[r for r in rules if
             isinstance(r,dict) and all(isinstance(r.get(k),str) for k in CONTEXT_KEYS)
             and tuple(r[k].casefold().strip() for k in CONTEXT_KEYS)==normalized]
    return matches[0] if len(matches)==1 else None

def assess_reviewed_rule(rule, *, dose, unit, frequency, weight_kg=None):
    """Return screening flags only; a below-threshold value never means safe."""
    unresolved={'status':'NOT_EVALUATED','clinical_clearance':False,
                'reason':'Missing exact reviewed rule, unit, or valid administered dose context'}
    if (not isinstance(rule,dict) or type(frequency) is not int or
        not 1<=frequency<=24 or not _positive_finite_number(dose) or
        not all(_positive_finite_number(rule.get(k)) for k in ('max_single','max_daily'))):
        return unresolved
    # Mass conversions are dimensionally exact; volume-to-mass conversion is
    # deliberately forbidden without formulation-specific concentration.
    mass_to_mg={'mcg':0.001,'mg':1.0,'g':1000.0}
    if unit not in mass_to_mg or rule.get('dose_unit') not in mass_to_mg:
        return unresolved
    normalized_dose=dose * mass_to_mg[unit] / mass_to_mg[rule['dose_unit']]
    if not math.isfinite(normalized_dose) or normalized_dose<=0:
        return unresolved
    if rule.get('review_status') not in (None,'APPROVED_BY_QUALIFIED_REVIEWER'):
        return unresolved
    weighted=('max_single_mg_per_kg' in rule or 'max_daily_mg_per_kg' in rule)
    if weighted and (unit!='mg' or not _positive_finite_number(weight_kg) or
                     not all(_positive_finite_number(rule.get(k)) for k in
                             ('max_single_mg_per_kg','max_daily_mg_per_kg'))):
        return {**unresolved,'reason':'Valid verified weight and matching mg/kg thresholds are required'}
    max_single=float(rule['max_single'])
    max_daily=float(rule['max_daily'])
    if weighted:
        max_single=min(max_single,float(rule['max_single_mg_per_kg'])*weight_kg)
        max_daily=min(max_daily,float(rule['max_daily_mg_per_kg'])*weight_kg)
    total=normalized_dose*frequency
    if not math.isfinite(total):
        return unresolved
    exceeded=normalized_dose>max_single or total>max_daily
    return {
        'status':'REVIEW_THRESHOLD_EXCEEDED' if exceeded
                 else 'BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY',
        'source_url':rule.get('source_url'),'source_section':rule.get('source_section'),
        'reviewer':rule.get('reviewer'),'rule_version':rule.get('version'),
        'dose_unit':rule['dose_unit'],'reported_dose':dose,'reported_unit':unit,
        'administered_single':normalized_dose,'administered_daily':total,
        'reviewed_max_single':max_single,'reviewed_max_daily':max_daily,
        'weight_based':weighted,
        'reviewed_adverse_effects':list(rule.get('overdose_adverse_effects',[])) if exceeded else [],
        'clinical_clearance':False
    }
