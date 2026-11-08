"""Metadata contract for one retained wall failure; no numerical imports."""
import hashlib
import json
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROTOCOL = 'experiments/s04b_wall_failure_continuation/protocol.json'
INDEX_SCHEMA = 'joint_exposure_refinement_operational_index_v1'
FAILURE = 'S6_narrow_short_total_seed410615'


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    def pairs(rows):
        value = {}
        for key,item in rows:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(root, relative):
    require(isinstance(relative,str) and relative and '\\' not in relative and ':' not in relative,
            'Unsafe relative path')
    part=PurePosixPath(relative);path=(Path(root)/relative).resolve()
    require(not part.is_absolute() and '..' not in part.parts and str(part)==relative
            and path.is_relative_to(Path(root).resolve()), 'Path escapes root')
    return path


def write_new(path, value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def reference(relative):
    return {'path':relative,'sha256':sha(safe(REPO,relative))}


def resolve(ref):
    require(set(ref)=={'path','sha256'},'Exact public path/hash reference required')
    path=safe(REPO,ref['path']);require(sha(path)==ref['sha256'],'Reference changed: '+ref['path'])
    return path


def verify_protocol():
    p=read(REPO/PROTOCOL)
    require(p['schema']=='joint_wall_failure_continuation_protocol_v1'
            and p['version']=='wall_failure_continuation_v1','Unknown operational policy')
    old=read(resolve(p['numerical_protocol']));resolve(p['scientific_protocol'])
    require(p['shared_run']==old['shared_run'] and p['original_native']==old['original_native']
            and p['full_sequence']==old['full_sequence'] and p['case_ids']==old['full_sequence'][56:]
            and p['case_slots']==old['case_slots'][12:] and p['hosts']==old['resources']['future_hosts'][4:],
            'Original roster/resources changed')
    require(len(p['case_ids'])==24 and p['full_sequence'][55]==p['failure']['case_id']==FAILURE
            and [g['host'] for g in p['hosts']]==[5,6,7,8]
            and [name for g in p['hosts'] for name in g['case_ids']]==p['case_ids'], 'Only untouched fixed hosts admitted')
    for name,pin in {**p['core_source_sha256'],**p['design_evidence']}.items():
        require(sha(safe(REPO,name))==pin,'Reviewed dependency changed: '+name)
    names=p['producer_source_paths']
    require(names==sorted(set(names)) and PROTOCOL in names,'Producer graph differs')
    for key in ('archive','review'):resolve(p['base'][key])
    audit=read(resolve(p['base']['review']))
    require(audit['passed'] is False and audit['audit_passed'] is True
            and audit['accepted_completed_prefix']['audit_passed'] is True
            and audit['accepted_completed_prefix']['processed_histories']==55
            and audit['accepted_completed_prefix']['complete_histories']==54
            and audit['accepted_completed_prefix']['new_complete_cases']==p['full_sequence'][51:55]
            and audit['scientific_completion'] is False
            and audit['live_agent_review'] is True and audit['live_agent_review_performed'] is True
            and audit['artifact_sha256']==p['base']['archive']['sha256']
            and audit['index_sha256']==p['base']['index_sha256'], 'Original failure audit changed')
    return p


def source_identity():
    p=verify_protocol();result=dict(p['core_source_sha256'])
    for name in p['producer_source_paths']:
        pin=sha(safe(REPO,name))
        require(name not in result or result[name]==pin,'Source graph conflict')
        result[name]=pin
    return dict(sorted(result.items()))


def operational_reference():
    return reference(PROTOCOL)
