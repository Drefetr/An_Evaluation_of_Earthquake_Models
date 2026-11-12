"""Validate the completed joint comparison from immutable saved outputs only.

This publication adapter does not fit, simulate, integrate likelihoods or weaken
the historical disposition validator. It reconstructs all displayed aggregate
fields and verifies every source-bound case before exporting the completed view.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import math
import statistics
import zipfile

DIRECTORY='validation/live_results/s04b_joint_complete_20261111'
REVIEW='validation/publication_refresh_20261112/joint_publication_review.json'
AUDIT='validation/live_results/s04b_joint_complete_independent_audit_20261111.json'
PROTOCOL='experiments/s04b_joint_nuisance/protocol.json'
REQUIRED_REVIEWED_SOURCES={'website/current_joint_results.py','website/build_findings.py',
    'tests/test_current_joint_publication.py'}

def require(value,message):
    if not value:raise ValueError(message)

def digest(raw):return hashlib.sha256(raw).hexdigest()

def document(raw):
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'Duplicate JSON key: '+k);d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+v)))

def aggregate(reports,protocol):
    """Independent arithmetic over the saved outcomes; no producer imports."""
    result=[]
    for regime in range(4,8):
        group=[r for r in reports if r['regime']==regime]
        require(len(group)==20,'Twenty completed histories required per regime')
        for model in ('LI','LIplus_immigrant','LIplus_inclusive'):
            for gate in (('raw',) if model=='LI' else ('raw','BIC')):
                rows=[next(v for v in r['outcomes'] if (v['model'],v['gate'])==(model,gate)) for r in group]
                gains=[v['new_gain'] for v in rows];wins=sum(g>0 for g in gains)
                z=1.959963984540054;p=wins/20;den=1+z*z/20
                center=(p+z*z/40)/den;half=z*math.sqrt(p*(1-p)/20+z*z/1600)/den
                result.append(dict(regime=regime,model=model,gate=gate,N=20,
                    mean_gain=math.fsum(gains)/20,median_gain=statistics.median(gains),wins=wins,
                    wilson95=[max(0.,center-half),min(1.,center+half)],
                    wilson_scope='pointwise bounded-win interval, not simultaneous or mean-gain inference',
                    near_zero=sum(v['near_zero'] for v in rows),
                    positive_near_zero=sum(v['near_zero'] and v['new_win'] for v in rows),
                    robust_positive=sum(v['robust_positive'] for v in rows),
                    robust_negative=sum(v['robust_negative'] for v in rows),
                    off_floor=sum(v['off_floor'] for v in rows),floor_returns=sum(v['floor_return'] for v in rows),unknowns=0,
                    a_boundary=sum(v['boundaries'][0] is not None for v in rows),
                    eta_lower=sum(v['boundaries'][5]=='lower' for v in rows),
                    eta_upper=sum(v['boundaries'][5]=='upper' for v in rows),
                    null_search_gap_cases=sum(bool(r['fits'][model]['null_search_gaps']) for r in group),
                    coarse_fine_gate_disagreements=sum(v['coarse_fine_gate_disagreement'] for v in rows),
                    optimizer_failed_attempts=sum(not v['success'] for r in group for arm in ('null',model) for v in r['fits'][arm]['records']),
                    coordinate_boundaries={name:{side:sum(v['boundaries'][i]==side for v in rows) for side in ('lower','upper')} for i,name in enumerate(protocol['coordinates'])},
                    realized_thinning={name:sum(r['thinning'][name] for r in group) for name in ('accepted_immigrants','rejected_immigrants','accepted_offspring','rejected_offspring')},
                    mean_training_events=sum(r['n_train'] for r in group)/20,
                    mean_test_events=sum(r['n_test'] for r in group)/20,
                    primary=(regime,model,gate) in ((5,'LIplus_immigrant','raw'),(7,'LIplus_inclusive','raw'))))
    return result

def equal(actual,expected,path='summary'):
    if isinstance(expected,dict):
        require(isinstance(actual,dict) and actual.keys()==expected.keys(),'Completed fields differ: '+path)
        for k,v in expected.items():equal(actual[k],v,path+'/'+k)
    elif isinstance(expected,list):
        require(isinstance(actual,list) and len(actual)==len(expected),'Completed list differs: '+path)
        for i,v in enumerate(expected):equal(actual[i],v,path+'/'+str(i))
    elif isinstance(expected,float):
        require(isinstance(actual,(int,float)) and math.isfinite(actual) and abs(actual-expected)<=1e-10,'Completed arithmetic differs: '+path)
    else:require(actual==expected,'Completed value differs: '+path)

def validate(repository):
    root=Path(repository).resolve();base=root/DIRECTORY
    if not base.exists():return None,{}
    pins={};archives={}
    def raw(relative,expected=None):
        path=(root/relative).resolve()
        require(not Path(relative).is_absolute() and path.is_relative_to(root),'Publication path escapes repository')
        data=path.read_bytes();pin=digest(data)
        require(expected is None or pin==expected,'Completed publication hash differs: '+relative)
        pins[relative]=pin;return data
    try:
        review=document(raw(REVIEW));require(review['passed'] is True and review['review_kind']=='completed_joint_publication_source_and_saved_output_review','Completed publication review required')
        require(REQUIRED_REVIEWED_SOURCES<=set(review['reviewed_files_sha256']),
            'Completed publication review omits required sources')
        for name,pin in review['reviewed_files_sha256'].items():raw(name,pin)
        summary=document(raw(DIRECTORY+'/summary.json',review['summary_sha256']))
        audit=document(raw(AUDIT,review['independent_audit_sha256']));protocol=document(raw(PROTOCOL))
        require(summary['schema']=='s04b_joint_complete_20261111' and summary['scientific_completion'] is True,'Completed scientific authority required')
        require(summary['completed_histories']==80 and summary['completed_outcomes']==400,'Completed census differs')
        require(audit['passed'] is True and audit['summary_sha256']==pins[DIRECTORY+'/summary.json'] and audit['missing_cells']==0,'Independent completed audit differs')
        require(audit['table_sha256']==digest(raw('paper/source/chapters/13_s04b_joint_dispositions.tex')),'Current joint table differs from independent review')
        require(len(summary['case_sources'])==80 and len({c['case_id'] for c in summary['case_sources']})==80,'Completed case roster differs')
        reports=[]
        for item in summary['case_sources']:
            case_id=item['case_id'];require(case_id in protocol['roster'],'Unknown completed history')
            case=document(raw(DIRECTORY+'/cases/'+case_id+'.json',item['sha256']))
            source=item['source']
            if 'member' in source:
                member=PurePosixPath(source['member'])
                require(not member.is_absolute() and '..' not in member.parts,'Unsafe completed archive member')
                if source['path'] not in archives:
                    raw(source['path'],source['sha256'])
                    archives[source['path']]=zipfile.ZipFile(root/source['path'])
                else:require(pins[source['path']]==source['sha256'],'Completed archive pin conflicts')
                archive=archives[source['path']]
                require(archive.namelist().count(source['member'])==1,'Duplicate completed source member')
                data=archive.read(source['member']);require(digest(data)==source['member_sha256'],'Completed source member differs')
            else:data=raw(source['path'],source['sha256'])
            require(document(data)==case,'Completed case differs from its original source')
            require(case['case_id']==case_id and case['passed'] is True and case['training_selections_frozen'] is True,'Unaccepted completed case')
            require(set(case['fits'])=={'null','LI','LIplus_immigrant','LIplus_inclusive'} and
                set(case['training_checks'])==set(case['fits']),'Completed arm roster differs')
            require(len(case['outcomes'])==5 and len({(v['model'],v['gate']) for v in case['outcomes']})==5 and
                all(v['passed'] and v['resolved_starts']==[True]*8 for v in case['fits'].values()) and
                all(v['passed'] for v in case['training_checks'].values()),'Incomplete completed case')
            for row in case['outcomes']:
                require(row['new_win']==(row['new_gain']>0),'Completed strict-win indicator differs')
                require(abs(row['new_gain']-(row['score']['joint']-row['new_null_score']['joint']))<1e-9,'Completed score identity differs')
            reports.append(case)
        equal(summary['summary'],aggregate(reports,protocol))
        require(sorted(r['case_id'] for r in reports)==sorted(protocol['roster']),'Completed roster does not cover the frozen protocol')
        return summary,pins
    finally:
        for archive in archives.values():archive.close()
