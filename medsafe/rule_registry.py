"""Fail-closed reviewed research threshold registry; never clinical clearance."""
from __future__ import annotations
from datetime import date
import json
import math
from pathlib import Path
from urllib.parse import urlparse

REQUIRED = ('ingredient','product_identifier','route','indication','population','dose_unit','max_single','max_daily','source_url','source_section','reviewer','review_date','version')

class RuleRegistryError(ValueError):
    pass

def _positive_finite_number(value):
    return type(value) in (int,float) and math.isfinite(value) and value > 0

def load_reviewed_rules(path: str | Path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
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
            raise RuleRegistryError(f'Rule {i} is not approved')
        if entry['dose_unit'] not in ('mg','mcg','g'):
            raise RuleRegistryError(f'Rule {i} invalid dose unit')
        url=urlparse(entry['source_url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise RuleRegistryError(f'Rule {i} invalid HTTPS evidence URL')
        try:
            reviewed=date.fromisoformat(entry['review_date'])
        except (TypeError,ValueError) as exc:
            raise RuleRegistryError(f'Rule {i} invalid review date') from exc
        if reviewed>date.today():
            raise RuleRegistryError(f'Rule {i} review date is in the future')
        lo,hi=entry.get('min_age_years'),entry.get('max_age_years')
        if lo is not None or hi is not None:
            if (type(lo) not in (int,float) or type(hi) not in (int,float) or
                not math.isfinite(lo) or not math.isfinite(hi) or not 0<=lo<=hi<=120):
                raise RuleRegistryError(f'Rule {i} invalid age interval')
        key=tuple(entry[k].casefold().strip() for k in ('ingredient','product_identifier','route','indication','population'))
        if key in seen:
            raise RuleRegistryError(f'Rule {i} duplicates an existing context')
        seen.add(key)
        result.append(entry)
    return result

def match_rule(rules, *, ingredient, product_identifier, route, indication, population):
    target=(ingredient,product_identifier,route,indication,population)
    if not all(isinstance(v,str) and v.strip() for v in target):
        return None
    keys=('ingredient','product_identifier','route','indication','population')
    matches=[r for r in rules if tuple(r[k].casefold().strip() for k in keys)==tuple(v.casefold().strip() for v in target)]
    return matches[0] if len(matches)==1 else None

def assess_reviewed_rule(rule, *, dose, unit, frequency):
    if (not rule or unit!=rule['dose_unit'] or type(frequency) is not int or
        not 1<=frequency<=24 or not _positive_finite_number(dose) or
        not all(_positive_finite_number(rule.get(k)) for k in ('max_single','max_daily'))):
        return {'status':'NOT_EVALUATED','reason':'Missing exact matching reviewed rule, unit or valid dose context'}
    exceeds=dose>rule['max_single'] or dose*frequency>rule['max_daily']
    return {'status':'REVIEW_THRESHOLD_EXCEEDED' if exceeds else 'BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY',
            'source_url':rule['source_url'],'reviewer':rule['reviewer'],
            'rule_version':rule['version'],'clinical_clearance':False}
