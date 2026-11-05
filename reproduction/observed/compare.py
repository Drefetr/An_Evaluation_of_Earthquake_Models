"""Strict comparison of a completed observed fit with the full historical record."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path,PurePosixPath
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def digest(payload):return hashlib.sha256(payload).hexdigest()


def strict_json(payload):
    def constant(value):raise ValueError('nonfinite_json_constant')
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('duplicate_json_key')
            result[key]=value
        return result
    return json.loads(payload,parse_constant=constant,object_pairs_hook=pairs)


def inside(root,name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
        raise ValueError('unsafe_manifest_path')
    result=(Path(root)/path).resolve()
    if not result.is_relative_to(Path(root).resolve()):raise ValueError('unsafe_manifest_path')
    return result


def read_pinned(path,expected_sha,expected_bytes=None):
    payload=Path(path).read_bytes()
    if digest(payload)!=expected_sha or (expected_bytes is not None and len(payload)!=expected_bytes):
        raise ValueError('input_hash_or_size_mismatch: '+Path(path).name)
    return payload


def load_manifest():return strict_json((HERE/'manifest.json').read_bytes())


def unpack(record):
    compressed=read_pinned(inside(HERE,record['path']),record['sha256'],record['bytes'])
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        payload=stream.read(record['original_bytes']+1)
    if len(payload)!=record['original_bytes'] or digest(payload)!=record['original_sha256']:
        raise ValueError('decompressed_result_identity_mismatch')
    return strict_json(payload),payload


def pointer(parts):return '/'+('/'.join(str(x).replace('~','~0').replace('/','~1') for x in parts))


def at(value,path):
    for segment in path[1:].split('/'):
        key=segment.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def compare_records(actual,expected,manifest):
    """All differences are reported; only explicitly enumerated metadata vary."""
    issues=[]
    ignored=set(manifest['timing_json_pointers']+manifest['metadata_json_pointers'])
    metadata_changes=[]
    for path in manifest['timing_json_pointers']:
        try:value=at(actual,path)
        except (KeyError,IndexError,TypeError,ValueError):
            issues.append({'path':path,'kind':'missing_timing_metadata'});continue
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            issues.append({'path':path,'kind':'invalid_timing_metadata'})
    identities=[('/protocol_sha256',manifest['current_protocol']['sha256']),
                ('/input_binding',manifest['required_input_binding']),
                ('/array_binding',manifest['required_array_binding']),
                ('/source_hashes',manifest['runtime_source_hashes'])]
    for path,wanted in identities:
        try:matches=at(actual,path)==wanted
        except (KeyError,IndexError,TypeError):matches=False
        if not matches:issues.append({'path':path,'kind':'identity_mismatch'})
    environment=actual.get('environment',{})
    if (not isinstance(environment,dict) or set(environment)!=set(expected['environment'])
            or type(environment.get('native_threads')) is not int or environment.get('native_threads')!=1
            or any(not isinstance(environment.get(k),str) or not environment[k] for k in ('python','numpy','scipy','pandas'))):
        issues.append({'path':'/environment','kind':'invalid_runtime_metadata'})
    try:
        start=datetime.fromisoformat(actual['started_utc'])
        end=datetime.fromisoformat(actual['completed_utc'])
        if start.utcoffset()!=timezone.utc.utcoffset(start) or end.utcoffset()!=timezone.utc.utcoffset(end) or end<start:
            raise ValueError('invalid_utc_order')
    except (KeyError,TypeError,ValueError):issues.append({'path':'/started_utc','kind':'invalid_utc_interval'})
    if actual.get('complete') is not True or actual.get('status')!='complete' or actual.get('synthetic_only') is not False:
        issues.append({'path':'/complete','kind':'incomplete_or_wrong_run_kind'})
    for name,fold in actual.get('folds',{}).items():
        if not isinstance(fold,dict) or fold.get('complete') is not True or fold.get('status')!='complete':
            issues.append({'path':'/folds/'+name,'kind':'incomplete_fold'})
            continue
        fit=fold.get('fit',{})
        if not isinstance(fit,dict) or fit.get('complete') is not True or fit.get('all_required_start_slots_accepted') is not True:
            issues.append({'path':'/folds/'+name+'/fit','kind':'incomplete_search'})
        for group in ('training_controls','test_controls'):
            controls=fold.get(group,{})
            if not isinstance(controls,dict) or not controls or any(not isinstance(c,dict) or c.get('pass') is not True for c in controls.values()):
                issues.append({'path':'/folds/'+name+'/'+group,'kind':'failed_or_missing_controls'})
    counts={'leaves':0,'numeric':0,'numeric_differences':0,'metadata_paths_excluded':len(ignored)}
    differences=[]
    maximum=0.0
    maximum_paths=[]

    def walk(a,b,parts=()):
        nonlocal maximum,maximum_paths
        path=pointer(parts)
        if type(a)!=type(b):
            differences.append({'path':path,'kind':'type','actual_type':type(a).__name__,'expected_type':type(b).__name__});return
        if path in ignored:
            if a!=b:metadata_changes.append({'path':path,'actual':a,'historical':b})
            return
        if isinstance(b,dict):
            for key in sorted(set(b)-set(a)):differences.append({'path':pointer(parts+(key,)),'kind':'missing_field'})
            for key in sorted(set(a)-set(b)):differences.append({'path':pointer(parts+(key,)),'kind':'unexpected_field'})
            for key in sorted(set(a)&set(b)):walk(a[key],b[key],parts+(key,))
        elif isinstance(b,list):
            if len(a)!=len(b):differences.append({'path':path,'kind':'list_length','actual':len(a),'expected':len(b)})
            for index,(x,y) in enumerate(zip(a,b)):walk(x,y,parts+(index,))
        else:
            counts['leaves']+=1
            if type(b) in (int,float):
                counts['numeric']+=1
                if not math.isfinite(a):
                    differences.append({'path':path,'kind':'nonfinite_value'});return
                if a!=b:
                    counts['numeric_differences']+=1
                    error=abs(a-b)
                    if error>maximum:maximum,maximum_paths=error,[path]
                    elif error==maximum:maximum_paths.append(path)
                    differences.append({'path':path,'kind':'numeric_value','actual':a,'historical':b,'absolute_difference':error})
            elif a!=b:differences.append({'path':path,'kind':'value','actual':a,'historical':b})
    walk(actual,expected)
    if counts['numeric']!=manifest['expected_scientific_numeric_leaves'] or counts['leaves']!=manifest['expected_scientific_leaves']:
        issues.append({'path':'/','kind':'scientific_field_count_mismatch'})
    return {'passed':not issues and not differences,'scientific_exact':not differences,
            'counts':counts,'identity_and_completion_issues':issues,'scientific_differences':differences,
            'maximum_absolute_numeric_difference':maximum,'maximum_difference_paths':maximum_paths,
            'metadata_changes':metadata_changes,
            'interpretation':'Exact equality of the full retained scientific record is required; no optimizer equivalence is inferred from a score tolerance.'}


def verify_repository(manifest,root=ROOT):
    protocol_ref=manifest['current_protocol']
    protocol=strict_json(read_pinned(inside(root,protocol_ref['path']),protocol_ref['sha256']))
    if protocol['source_hashes']!=manifest['all_protocol_source_hashes']:
        raise ValueError('protocol_source_roster_mismatch')
    checks=[]
    for path,expected in protocol['source_hashes'].items():
        payload=read_pinned(inside(Path(root)/'engine',path),expected)
        checks.append({'path':'engine/'+path,'sha256':digest(payload)})
    csv_payload=read_pinned(inside(root,manifest['bundled_csv']),manifest['required_input_binding']['sha256'])
    return {'protocol_sha256':protocol_ref['sha256'],'csv_sha256':digest(csv_payload),'source_checks':checks}


def run_comparison(actual_path=None,root=ROOT):
    manifest=load_manifest()
    expected,expected_payload=unpack(manifest['historical_result'])
    if expected['protocol_sha256']!=manifest['historical_protocol_sha256']:
        raise ValueError('historical_protocol_identity_mismatch')
    if actual_path is None:actual,payload=unpack(manifest['completed_refit'])
    else:
        payload=Path(actual_path).read_bytes()
        actual=strict_json(payload)
    repository=verify_repository(manifest,root)
    result=compare_records(actual,expected,manifest)
    result.update(schema_version=1,actual_result_sha256=digest(payload),historical_result_sha256=digest(expected_payload),
                  manifest_sha256=digest((HERE/'manifest.json').read_bytes()),repository_identity=repository,
                  actual_environment=actual.get('environment'),historical_environment=expected.get('environment'),
                  scope='Comparison of saved complete fitted/control records; comparison itself does not execute a fit.')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual',type=Path,help='Completed observed.json; default is the bundled actual refit.')
    parser.add_argument('--output',type=Path,required=True,help='New report file; existing files are refused.')
    args=parser.parse_args(argv)
    if args.output.exists():print('Refusing to overwrite comparison report',file=sys.stderr);return 2
    try:result=run_comparison(args.actual)
    except Exception as error:result={'schema_version':1,'passed':False,'error_type':type(error).__name__,'error':str(error)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'passed':result['passed'],'counts':result.get('counts'),'report':args.output.name}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
