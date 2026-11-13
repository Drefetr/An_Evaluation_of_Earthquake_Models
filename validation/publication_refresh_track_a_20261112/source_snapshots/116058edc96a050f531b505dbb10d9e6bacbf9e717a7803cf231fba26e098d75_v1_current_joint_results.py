"""Validate the completed joint comparison from immutable saved outputs only.

This publication adapter does not fit, simulate, integrate likelihoods or weaken
the historical disposition validator. It reconstructs all displayed aggregate
fields and verifies every source-bound case before exporting the completed view.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import math
import re
import statistics
import zipfile

DIRECTORY='validation/live_results/s04b_joint_complete_20261111'
REVIEW='validation/publication_refresh_track_a_20261112/joint_publication_review.json'
AUDIT='validation/live_results/s04b_joint_complete_independent_audit_20261111.json'
PROTOCOL='experiments/s04b_joint_nuisance/protocol.json'
REQUIRED_REVIEWED_SOURCES={'website/current_joint_results.py','website/build_findings.py',
    'tests/test_current_joint_publication.py'}
TABLE='paper/source/chapters/13_s04b_joint_dispositions.tex'

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

def validate_presentation(reference,raw,root,audit,summary,reports):
    """An additive presentation epoch preserves the old audited table exactly.

    A changed current table is admitted only after verifying its archived
    predecessor, the unchanged scientific summary/audit and independently
    recomputed MCSE/event counts. All three current tables are then checked
    cell by cell, excluding the four explicit regime subheaders from row counts.
    """
    require(set(reference)=={'path','sha256'},'Presentation path/hash reference required')
    p=document(raw(reference['path'],reference['sha256']))
    require(p['schema']=='completed_joint_presentation_overlay_v1','Unknown presentation overlay')
    for key,expected in [('summary',DIRECTORY+'/summary.json'),('scientific_audit',AUDIT),('current_table',TABLE)]:
        ref=p[key];require(ref['path']==expected,'Presentation source identity differs: '+key)
        raw(ref['path'],ref['sha256'])
    require(p['summary']['sha256']==digest((root/(DIRECTORY+'/summary.json')).read_bytes()),'Presentation summary binding differs')
    preceding=document(raw(p['preceding_publication_review']['path'],p['preceding_publication_review']['sha256']))
    require(preceding['passed'] is True and preceding['summary_sha256']==p['summary']['sha256'] and
        preceding['independent_audit_sha256']==p['scientific_audit']['sha256'],'Preceding scientific review differs')
    archive_ref=p['archived_table'];raw(archive_ref['path'],archive_ref['sha256'])
    member=PurePosixPath(archive_ref['member'])
    require(not member.is_absolute() and '..' not in member.parts and str(member)==TABLE,'Archived table member differs')
    with zipfile.ZipFile(root/archive_ref['path']) as archive:
        require(archive.namelist().count(str(member))==1,'Archived table member is not unique')
        original=archive.read(str(member))
    require(digest(original)==archive_ref['member_sha256']==audit['table_sha256'],
        'Original scientific table audit no longer holds')
    supplement=document(raw(p['mcse_supplement']['path'],p['mcse_supplement']['sha256']))
    table_audit=document(raw(p['table_audit']['path'],p['table_audit']['sha256']))
    require(table_audit['passed'] is True,'Additive table computational audit required')
    require(table_audit['authority_path']==p['mcse_supplement']['path'] and
        table_audit['authority_sha256']==p['mcse_supplement']['sha256'] and
        table_audit['manuscript_sha256'][TABLE]==p['current_table']['sha256'],
        'Additive table computational audit identities differ')
    for ref in supplement['source_files']:raw(ref['path'],ref['sha256'])
    rows=supplement['joint_rows'];regimes=supplement['regimes']
    require(len(rows)==20 and len({(r['regime'],r['model'],r['gate']) for r in rows})==20,'Presentation MCSE roster differs')
    require(len(regimes)==4 and {r['regime'] for r in regimes}==set(range(4,8)),'Presentation regime census differs')
    for row,old in zip(rows,summary['summary']):
        key=(row['regime'],row['model'],row['gate'])
        require(key==(old['regime'],old['model'],old['gate']),'Presentation procedure ordering differs')
        equal(row['primary'],old['primary'],'presentation/primary')
        equal(row['N'],old['N'],'presentation/N')
        values=[next(v['new_gain'] for v in case['outcomes'] if (v['model'],v['gate'])==key[1:])
            for case in sorted(reports,key=lambda r:r['case_id']) if case['regime']==key[0]]
        equal(sorted(row['values']),sorted(values),'presentation/gains')
        equal(row['mean'],math.fsum(values)/20,'presentation/mean')
        equal(row['mcse'],statistics.stdev(values)/math.sqrt(20),'presentation/mcse')
        equal(row['sample_sd'],statistics.stdev(values),'presentation/sample_sd')
        equal(row['median'],statistics.median(values),'presentation/median')
        equal(row['wins'],sum(v>0 for v in values),'presentation/wins')
        equal(row['wilson95'],old['wilson95'],'presentation/wilson')
    for regime in regimes:
        cases=sorted([r for r in reports if r['regime']==regime['regime']],key=lambda r:r['case_id'])
        equal(regime['N'],len(cases),'presentation/regime_N')
        equal(regime['case_ids'],[r['case_id'] for r in cases],'presentation/cases')
        for phase in ('train','test'):
            equal(regime['n_'+phase],[r['n_'+phase] for r in cases],'presentation/counts')
            equal(regime['mean_n_'+phase],math.fsum(r['n_'+phase] for r in cases)/20,'presentation/mean_count')
    text=raw(TABLE,p['current_table']['sha256']).decode('utf-8')
    def body(label):
        marker='\\label{'+label+'}'
        require(text.count(marker)==1,'Current presentation table label differs')
        return text.split(marker,1)[1].split('\\end{table}',1)[0]
    def cells(label):
        return [[c.strip() for c in line.strip().removesuffix('\\\\').strip().split('&')]
            for line in body(label).splitlines() if re.match(r'^\s*S[4-7]\s*&',line)]
    def label(row):
        return {'LI':'LI','LIplus_immigrant':'LI+ immigrant','LIplus_inclusive':'LI+ total'}[row['model']]+' ('+row['gate']+')'+('$^{\\dagger}$' if row['primary'] else '')
    scores=cells('tab:s04b-joint-disposition-scores')
    expected=[['S'+str(r['regime']),label(r),'20/20',f"{r['mean']:.4f}",f"{r['mcse']:.4f}",
        f"{r['median']:.4f}",str(r['wins'])+'/20','['+', '.join(f'{v:.4f}' for v in r['wilson95'])+']'] for r in rows]
    require(scores==expected,'Current MCSE score-table cells differ')
    headers=[line.strip() for line in body('tab:s04b-joint-disposition-scores').splitlines() if '\\multicolumn' in line]
    expected_headers=[r'\multicolumn{8}{@{}l}{\textbf{S'+str(r['regime'])+r'}: mean $N_{\mathrm{train}}='+f"{r['mean_n_train']:.2f}"+r'$, $N_{\mathrm{test}}='+f"{r['mean_n_test']:.2f}"+r'$} \\' for r in regimes]
    require(headers==expected_headers,'Current event-count subheaders differ')
    diagnostics=[];floors=[]
    for r in summary['summary']:
        prefix=['S'+str(r['regime']),label(r)]
        diagnostics.append(prefix+['0',str(r['coordinate_boundaries']['a']['lower'])+'/'+str(r['coordinate_boundaries']['a']['upper']),
            str(r['eta_lower'])+'/'+str(r['eta_upper']),str(r['optimizer_failed_attempts']),str(r['null_search_gap_cases']),str(r['coarse_fine_gate_disagreements'])])
        floors.append(prefix+[str(r[k]) for k in ('off_floor','floor_returns','near_zero','positive_near_zero','robust_positive','robust_negative')])
    require(cells('tab:s04b-joint-disposition-diagnostics')==diagnostics,'Current search-diagnostic table cells differ')
    require(cells('tab:s04b-joint-disposition-floor-census')==floors,'Current floor-census table cells differ')
    return dict(mcse_rows=rows,regimes=regimes,reviewed_tables=3,scientific_rows_per_table=20,regime_subheaders=4)

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
        current_table_sha=digest(raw(TABLE))
        presentation=review.get('presentation')
        require(audit['table_sha256']==current_table_sha or presentation is not None,
            'Current joint table differs from independent computational review')
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
        if presentation is not None:
            summary=dict(summary,presentation=validate_presentation(presentation,raw,root,audit,summary,reports))
        return summary,pins
    finally:
        for archive in archives.values():archive.close()
