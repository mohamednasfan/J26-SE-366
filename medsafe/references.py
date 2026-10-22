"""Live public drug-label lookup; deliberately does not extract clinical maximum doses."""
from __future__ import annotations
import re
from urllib.parse import quote
import requests

DM = 'https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json'
FDA = 'https://api.fda.gov/drug/label.json'
RXN = 'https://rxnav.nlm.nih.gov/REST/rxcui.json'


def _fetch(session, url, params):
    try:
        res = session.get(url, params=params, timeout=(3, 7), headers={'Accept': 'application/json'})
        if res.status_code == 404:
            return {'state': 'NOT_FOUND', 'results': []}
        res.raise_for_status()
        return {'state': 'OK', 'json': res.json()}
    except (requests.RequestException, ValueError, TypeError):
        return {'state': 'UNAVAILABLE', 'results': []}


def _same_name(title: str, name: str) -> bool:
    # Product titles often include salt, strength or manufacturer: don't assert exact drug identity.
    # Case-insensitive *whole-token* mention is only a search candidate.
    return bool(re.search(r'(?<![a-z0-9])' + re.escape(name.lower()) + r'(?![a-z0-9])', title.lower()))


def lookup(name: str, session=None) -> dict:
    """Provide candidates and official links; don't infer approval/safety from search hits."""
    if not name or not re.fullmatch(r'[A-Za-z][A-Za-z0-9\- ]{1,79}', name.strip()):
        return {'status': 'INVALID_QUERY', 'dailymed': [], 'openfda': [], 'errors': []}
    name = ' '.join(name.strip().split())
    session = session or requests.Session()
    dm = _fetch(session, DM, {'drug_name': name, 'pagesize': 5})
    entries = []
    if dm['state'] == 'OK' and isinstance(dm.get('json'), dict):
        for item in dm['json'].get('data', [])[:5]:
            if not isinstance(item, dict):
                continue
            title, sid = str(item.get('title', '')), str(item.get('setid', ''))
            if not _same_name(title, name) or not re.fullmatch(r'[a-zA-Z0-9-]{10,70}', sid):
                continue
            entries.append({'title': title[:160], 'setid': sid,
                            'url': f'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={quote(sid)}'})
    # Exact-name field search, not a wildcard; unmatched results are not accepted as validated drugs.
    fda = _fetch(session, FDA, {'search': f'openfda.generic_name.exact:"{name}"', 'limit': 3})
    fda_entries = []
    if fda['state'] == 'OK' and isinstance(fda.get('json'), dict):
        for label in fda['json'].get('results', [])[:3]:
            metadata = label.get('openfda', {}) if isinstance(label, dict) else {}
            generic_names = metadata.get('generic_name', [])
            if not any(n.lower().strip() == name.lower() for n in generic_names if isinstance(n, str)):
                continue
            setid = str(label.get('set_id', ''))
            sections={}
            for key in ('dosage_and_administration','pediatric_use','geriatric_use',
                        'contraindications','warnings','overdosage','adverse_reactions',
                        'drug_interactions'):
                raw=label.get(key,[]) if isinstance(label,dict) else []
                if isinstance(raw,list) and raw and isinstance(raw[0],str):
                    sections[key]=raw[0][:550]
            fda_entries.append({'name': name, 'setid': setid, 'label_sections_UNVERIFIED_FOR_PRODUCT':sections,
                                'url': f'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={quote(setid)}' if re.fullmatch(r'[a-zA-Z0-9-]{10,70}', setid) else 'https://open.fda.gov/apis/drug/label/'})
    # RxNorm exact-or-normalized concept search helps flag unrecognized drug
    # names. A negative result is NEVER proof that a drug is invalid.
    rxn = _fetch(session, RXN, {'name': name, 'search': '2', 'allsrc': '0'})
    rxn_ids = []
    if rxn['state'] == 'OK' and isinstance(rxn.get('json'), dict):
        group = rxn['json'].get('idGroup') or {}
        if isinstance(group,dict):
            rxn_ids = [str(i) for i in (group.get('rxnormId') or []) if str(i).isdigit()][:10]
    return {
        'status': ('REFERENCE_UNAVAILABLE' if all(x['state']=='UNAVAILABLE' for x in (dm, fda, rxn))
                   else 'CANDIDATES_FOUND' if entries or fda_entries or rxn_ids else 'NO_EXACT_MATCH_FOUND'),
        'rxnorm': {'concept_ids':rxn_ids, 'status': 'CANDIDATES_FOUND' if rxn_ids else 'UNAVAILABLE' if rxn['state']=='UNAVAILABLE' else 'NO_MATCH'},
        'dailymed': entries, 'openfda': fda_entries,
        'errors': [key for key, result in (('DailyMed', dm), ('openFDA', fda), ('RxNorm', rxn)) if result['state'] == 'UNAVAILABLE'],
        'dose_threshold_extracted': False,
        'note': 'RxNorm concepts and drug labels are identity candidates, not dosage or age-safety approvals.'
    }
