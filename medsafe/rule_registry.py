"""Reviewed-rule registry: empty by default. Never infer clinical limits from label search results."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

REQUIRED = ('ingredient','product_identifier','route','indication','population','dose_unit','max_single','max_daily','source_url','source_section','reviewer','review_date','version')

class RuleRegistryError(ValueError):
    pass

def load_reviewed_rules(path: str | Path):
    """Load provenance-complete human-reviewed rules, not unreviewed drug label snippets."""
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,list): raise RuleRegistryError('Rule registry must be a JSON list')
    result=[]
    for i,entry in enumerate(data):
        if not isinstance(entry,dict) or any(not entry.get(k) for k in REQUIRED):
            raise RuleRegistryError(f'Rule {i} missing required provenance or context')
        if entry.get('review_status')!='APPROVED_BY_QUALIFIED_REVIEWER':
            raise RuleRegistryError(f'Rule {i} is not approved')
        if entry['dose_unit'] not in ('mg','mcg','g') or any(type(entry[k]) not in (float,int) or entry[k]<=0 for k in ('max_single','max_daily')):
            raise RuleRegistryError(f'Rule {i} has invalid thresholds')
        if not str(entry['source_url']).startswith('https://'):
            raise RuleRegistryError(f'Rule {i} requires HTTPS source URL')
        try: date.fromisoformat(entry['review_date'])
        except (TypeError,ValueError): raise RuleRegistryError(f'Rule {i} invalid review date')
        result.append(entry)
    return result

def match_rule(rules, *, ingredient, product_identifier, route, indication, population):
    """Exact product, route, indication and population matching only; ambiguous -> none."""
    target=(ingredient,product_identifier,route,indication,population)
    matches=[r for r in rules if tuple(r[k].casefold().strip() for k in ('ingredient','product_identifier','route','indication','population'))==tuple(str(v).casefold().strip() for v in target)]
    return matches[0] if len(matches)==1 else None

def assess_reviewed_rule(rule, *, dose, unit, frequency):
    """Threshold flag, never clinical clearance; caller must verify product/context separately."""
    if not rule or unit!=rule['dose_unit'] or type(frequency) is not int or not 1<=frequency<=24 or type(dose) not in (int,float) or dose<=0:
        return {'status':'NOT_EVALUATED','reason':'Missing exact matching reviewed rule, unit or dose context'}
    return {'status':'REVIEW_THRESHOLD_EXCEEDED' if dose>rule['max_single'] or dose*frequency>rule['max_daily'] else 'BELOW_REVIEWED_THRESHOLD_NOT_PROOF_OF_SAFETY',
            'source_url':rule['source_url'],'reviewer':rule['reviewer'],'rule_version':rule['version'],'clinical_clearance':False}
