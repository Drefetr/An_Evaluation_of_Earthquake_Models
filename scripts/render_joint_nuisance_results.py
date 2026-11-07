"""Stage new TeX and additive claims only after complete joint-study acceptance.

No scientific module is imported, no fit or likelihood is evaluated, and no
manuscript, ledger, authority or provenance file is written by this command.
The final completion review is issued separately after Tasks 1–3 actually pass.
"""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path

PROCEDURES = [('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),
              ('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]
PRIMARY = {(5,'LIplus_immigrant','raw'),(7,'LIplus_inclusive','raw')}
LABELS = {'LI':r'LI', 'LIplus_immigrant':r'LI+ immigrant', 'LIplus_inclusive':r'LI+ total'}
PROTOCOL = 'experiments/s04b_joint_nuisance/protocol.json'
COUNTS = dict(unique_histories=80, comparisons=400, historical_comparisons=400, floor_checks=480, summary_rows=20)
COUNT_FIELDS = ('wins','off_floor','a_boundary','eta_lower','eta_upper','optimizer_failed_attempts',
                'unknowns','null_search_gap_cases','coarse_fine_gate_disagreements','floor_returns',
                'near_zero','positive_near_zero','robust_positive','robust_negative')


def require(condition,message):
    if not condition: raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key: '+key);result[key]=value
        return result
    return json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+value)))


def safe(root,relative):
    require(isinstance(relative,str) and relative and '\\' not in relative and ':' not in relative,
            'A portable repository-relative path is required')
    value=Path(relative);require(not value.is_absolute() and '..' not in value.parts,'Escaping input path')
    path=(root/value).resolve();require(path.is_relative_to(root.resolve()),'Escaping input path');return path


def numeric(value):
    require(type(value) in (int,float) and math.isfinite(value),'Expected finite non-boolean scalar')
    return value


def integer(value,maximum=None):
    require(type(value) is int and value>=0 and (maximum is None or value<=maximum),'Invalid census count')
    return value


def pointer(value,where):
    for token in where.removeprefix('/').split('/'):
        token=token.replace('~1','/').replace('~0','~')
        value=value[int(token)] if isinstance(value,list) else value[token]
    return value


def close(left,right):
    return abs(numeric(left)-numeric(right))<=1e-9


def validate(repository,paths):
    """Check saved evidence and acceptance; do not recompute research results."""
    documents={};resolved={};pins={}
    for key,relative in paths.items():
        require(relative.endswith('.json') and relative.startswith('validation/') and
                not relative.startswith(('validation/authorities/','provenance/')),'Public live JSON inputs are required')
        path=safe(repository,relative);resolved[key]=path;documents[key]=read(path);pins[relative]=sha(path)
    summary,result,index,audit,completion=(documents[k]for k in ('summary','result','index','audit','completion_review'))
    require(completion.get('schema')=='joint_nuisance_publication_acceptance_v1' and completion.get('passed') is True and
            completion.get('live_independent_review') is True and completion.get('scientific_completion') is True,
            'A genuine final live independent publication acceptance is required')
    require(completion.get('counts')==COUNTS,'Final accepted scientific counts differ')
    for key in ('summary','result','index','audit'):
        require(completion['artifact_sha256'].get(paths[key])==pins[paths[key]],'Final acceptance does not bind '+key)
    require(set(completion.get('tasks',{}))=={'task1','task2','task3'},'All three completion tasks are required')
    for name,task in completion['tasks'].items():
        require(task.get('passed') is True,'Incomplete '+name)
        reference=task['acceptance']
        require(reference['path'].startswith('validation/') and not reference['path'].startswith('validation/authorities/'),
                'Public live task acceptance is required')
        path=safe(repository,reference['path'])
        require(sha(path)==reference['sha256'] and read(path).get('passed') is True,'Task acceptance differs: '+name)
        pins[reference['path']]=sha(path)
    require(result.get('passed') is True and result.get('scientific_completion') is True and
            result.get('complete_cases')==80 and result.get('status')=='batch_complete','Incomplete final scientific result')
    require(result.get('index_sha256')==pins[paths['index']] and result.get('summary_sha256')==pins[paths['summary']],
            'Final result/index/summary identity differs')
    require(index.get('partial_case') is None and index.get('last_attempt_passed') is True,'Unresolved final index')
    require(audit.get('review_kind')=='live_agent_saved_output_review' and audit.get('live_agent_review') is True and
            audit.get('live_agent_review_performed',True) is True and
            audit.get('final_batch_agent_review_required',False) is False,
            'The bound final audit must itself be a completed live independent review')
    require(audit.get('passed') is True and audit.get('scientific_completion') is True and
            audit.get('complete_cases')==80 and audit.get('outcomes')==400 and audit.get('historical_floor_checks')==480 and
            audit.get('historical_comparison_rows')==400,'Incomplete independent scientific audit')
    for field,key in [('index_sha256','index'),('execution_result_sha256','result'),('summary_sha256','summary')]:
        require(audit.get(field)==pins[paths[key]],'Independent audit does not bind '+key)
    protocol_path=safe(repository,PROTOCOL);protocol=read(protocol_path);pins[PROTOCOL]=sha(protocol_path)
    require(index.get('science_protocol_sha256')==sha(protocol_path),'Frozen scientific protocol differs')
    entries=index['cases'];ids=[entry['case_id']for entry in entries]
    require(len(ids)==len(set(ids))==80 and set(ids)==set(protocol['roster']) and len(protocol['roster'])==80,
            'Exactly the frozen eighty unique histories are required')
    actual_counts=Counter();regimes=Counter()
    for entry in entries:
        path=safe(resolved['index'].parent,entry['file']);require(sha(path)==entry['sha256'],'Saved case bytes changed')
        report=read(path);require(report.get('passed') is True and report.get('status')=='complete' and
            report.get('case_id')==entry['case_id'],'Incomplete saved case')
        regime=integer(report['regime']);require(regime in (4,5,6,7),'Unknown regime');regimes[regime]+=1
        outcomes=report['outcomes'];historical=report['historical_comparisons'];floors=report['floor_checks']
        require(len(outcomes)==5 and {(r['model'],r['gate'])for r in outcomes}==set(PROCEDURES),'Missing/duplicate outcome')
        require(len(historical)==5 and {(r['model'],r['gate'])for r in historical}==set(PROCEDURES) and
                all(r.get('passed') is True for r in historical),'Historical comparison roster incomplete')
        require(len(floors)==6 and {(r['phase'],r['model'])for r in floors}==
                {(phase,model)for phase in ('train','test')for model in LABELS},'Historical floor check roster incomplete')
        for floor in floors:
            delta=abs(numeric(floor['actual_nll'])-numeric(floor['expected_nll']))
            require(floor['tolerance']==1e-9 and delta<=1e-9 and close(floor['absolute_delta'],delta),
                    'Historical full-precision floor check failed')
        for outcome in outcomes:
            gain=numeric(outcome['new_gain'])
            require(type(outcome['new_win']) is bool and outcome['new_win']==(gain>0) and
                    type(outcome['near_zero']) is bool and outcome['near_zero']==(abs(gain)<=1e-9),
                    'Strict win and separate near-zero definitions differ')
        actual_counts.update(comparisons=len(outcomes),historical_comparisons=len(historical),floor_checks=len(floors))
    require(regimes==Counter({4:20,5:20,6:20,7:20}) and actual_counts==Counter({k:COUNTS[k]for k in
        ('comparisons','historical_comparisons','floor_checks')}),'Actual case/check counts differ')
    expected={(regime,model,gate)for regime in (4,5,6,7)for model,gate in PROCEDURES}
    require(isinstance(summary,list) and len(summary)==20 and
            {(r['regime'],r['model'],r['gate'])for r in summary}==expected,'Twenty unique procedure summary rows are required')
    independent=audit['independent_summary'];require(len(independent)==20,'Missing independent summary')
    independent_by={(r['regime'],r['model'],r['gate']):r for r in independent}
    require(len(independent_by)==20 and set(independent_by)==expected,'Independent procedure roster differs')
    for row in summary:
        key=row['regime'],row['model'],row['gate'];checked=independent_by[key]
        require(type(row['N']) is int and row['N']==checked['N']==20,'Summary denominator differs')
        require(type(row['primary']) is bool and row['primary']==(key in PRIMARY),'Prespecified contrast classification differs')
        for name in ('mean_gain','median_gain'):
            require(close(row[name],checked[name]),'Summary differs from independent arithmetic: '+name)
        bounds=row['wilson95'];require(len(bounds)==2 and 0<=numeric(bounds[0])<=numeric(bounds[1])<=1,'Invalid Wilson interval')
        require(len(checked['wilson95'])==2 and all(close(x,y)for x,y in zip(bounds,checked['wilson95'])),
                'Independent Wilson interval differs')
        for field in COUNT_FIELDS:
            integer(row[field],None if field=='optimizer_failed_attempts' else 20)
            require(row[field]==checked[field],'Independent diagnostic census differs: '+field)
        require(row['unknowns']==0,'Unknown cases cannot be formatted as a completed study')
        require(row['near_zero']+row['robust_positive']+row['robust_negative']==20 and
                row['wins']==row['robust_positive']+row['positive_near_zero'] and
                row['positive_near_zero']<=row['near_zero'] and row['floor_returns']<=row['near_zero'],
                'Strict-win, floor-return and near-zero census disagree')
        for coordinate in ('a','eta'):
            values=row['coordinate_boundaries'][coordinate]
            require(set(values)=={'lower','upper'},'Boundary sides missing')
            require(sum(integer(values[side],20)for side in values)<=20,'Invalid boundary census')
            require(values==checked['coordinate_boundaries'][coordinate],'Independent coordinate census differs')
        require(row['a_boundary']==sum(row['coordinate_boundaries']['a'].values()) and
                row['eta_lower']==row['coordinate_boundaries']['eta']['lower'] and
                row['eta_upper']==row['coordinate_boundaries']['eta']['upper'],'Boundary summaries disagree')
    return summary,pins


def render(summary,summary_path,summary_sha,tex_location):
    claims={}
    def cell(index,field,places=None):
        location='/'+str(index)+'/'+field;value=numeric(pointer(summary,location))
        if places is None:
            integer(value);display=str(value)
        else:
            rounded=Decimal(str(value)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_EVEN)
            if rounded==0:rounded=abs(rounded)
            display=format(rounded,f'.{places}f')
        key=location+'|'+display
        if key not in claims:
            claims[key]=dict(id='s04b-joint-'+summary_sha[:12]+'-'+str(index).zfill(2)+'-'+field.replace('/','-'),
                bundled_source=summary_path,source_path=summary_path,source_sha256=summary_sha,
                json_pointer=location,resolved_source_value=value,display=display,
                transformation='decimal rounding to displayed precision',json_value_kind='numeric_scalar',
                ledger_role='manuscript_binding',final_display_locations=[tex_location],
                component='S04B jointly fitted temporal backbone and inhibition comparison',
                qualification='Completed fixed-roster fitted-procedure comparison; exact accepted summary pointer. Pointwise Wilson intervals concern wins, not mean-gain uncertainty.',
                status='source_bound',binding_kind='exact_json_pointer',value=value,
                reconciliation_status='staged_pending_manuscript_installation')
        return display
    order=sorted(range(len(summary)),key=lambda i:(summary[i]['regime'],PROCEDURES.index((summary[i]['model'],summary[i]['gate']))))
    def label(index):
        row=summary[index];text=LABELS[row['model']]+' ('+row['gate']+')'
        return text+(r'$^{\dagger}$' if row['primary'] else '')
    lines=[r'% Staged from the accepted joint study; this file is not installed automatically.',
        r'\begin{table}[htbp]',r'\centering',
        r'\caption{Held-out joint-score gains against the jointly fitted uninhibited floor, with the common spatial and mark laws held fixed. Means and medians are in nats. Wins use the saved strict-positive criterion; near-zero flags remain separate. Wilson intervals are pointwise win-rate intervals, not simultaneous intervals or uncertainty intervals for mean gains. Marked rows are the prespecified primary contrasts; other rows are descriptive. Off-floor counts use the saved positive-inhibition indicators.}',
        r'\label{tab:s04b-joint-nuisance-scores}',r'\begin{tabular}{llrrrrr}',r'\toprule',
        r'Regime & Procedure & Mean & Median & Wins & Wilson interval & Off-floor \\',r'\midrule']
    for i in order:
        lines.append('S'+cell(i,'regime')+' & '+label(i)+' & '+cell(i,'mean_gain',4)+' & '+cell(i,'median_gain',4)+
            ' & '+cell(i,'wins')+'/'+cell(i,'N')+' & ['+cell(i,'wilson95/0',4)+', '+cell(i,'wilson95/1',4)+'] & '+cell(i,'off_floor')+r' \\')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}','',r'\begin{table}[htbp]',r'\centering',
        r'\caption{Selected-state boundary and search diagnostics for the same procedures. Boundary pairs give lower/upper counts for the background intercept and inhibition strength. Failed attempts count unsuccessful optimizer returns for the shared null and named alternative; raw and gated rows reuse searches, so these counts must not be added across rows. Unknowns, null-search gaps, and coarse/fine gate disagreements remain explicit. A null-search gap prevents attributing a procedure contrast to inhibition.}',
        r'\label{tab:s04b-joint-nuisance-diagnostics}',r'\begin{tabular}{llrrrrrr}',r'\toprule',
        r'Regime & Procedure & $a$ bounds & $\eta$ bounds & Failed attempts & Unknown & Null gaps & Gate differences \\',r'\midrule'])
    for i in order:
        lines.append('S'+cell(i,'regime')+' & '+label(i)+' & '+cell(i,'coordinate_boundaries/a/lower')+'/'+cell(i,'coordinate_boundaries/a/upper')+
            ' & '+cell(i,'eta_lower')+'/'+cell(i,'eta_upper')+' & '+cell(i,'optimizer_failed_attempts')+' & '+cell(i,'unknowns')+
            ' & '+cell(i,'null_search_gap_cases')+' & '+cell(i,'coarse_fine_gate_disagreements')+r' \\')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}','',r'\begin{table}[htbp]',r'\centering',
        r'\caption{Floor-return and numerical-near-zero census for the same comparisons. The robust-positive and robust-negative categories use the frozen numerical tolerance; they are not statistical significance claims. Positive near-zero gains still count as strict wins. An alternative can return to zero inhibition with a better nuisance solution than the separately optimized null: such a gain is a procedure and optimizer contrast, not evidence of inhibition. The null-search-gap census is reported in Table~\ref{tab:s04b-joint-nuisance-diagnostics}.}',
        r'\label{tab:s04b-joint-nuisance-floor-census}',r'\begin{tabular}{llrrrrr}',r'\toprule',
        r'Regime & Procedure & Floor returns & Near zero & Positive near zero & Robust positive & Robust negative \\',r'\midrule'])
    for i in order:
        lines.append('S'+cell(i,'regime')+' & '+label(i)+' & '+cell(i,'floor_returns')+' & '+cell(i,'near_zero')+
            ' & '+cell(i,'positive_near_zero')+' & '+cell(i,'robust_positive')+' & '+cell(i,'robust_negative')+r' \\')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}',''])
    return '\n'.join(lines),list(claims.values())


def stage(repository,paths,output,tex_location):
    repository=repository.resolve();output=output.resolve()
    require(not output.is_relative_to(repository) and not output.exists(),'Fresh external staging directory required')
    require(tex_location.startswith('chapters/') and tex_location.endswith('.tex'),'New chapter TeX location required')
    destination=safe(repository/'paper/source',tex_location)
    require(not destination.exists(),'Existing manuscript source must not be replaced')
    summary,pins=validate(repository,paths)
    tex,claims=render(summary,paths['summary'],pins[paths['summary']],tex_location)
    ledger_path=repository/'validation/MASTER_CLAIM_LEDGER.json'
    if ledger_path.exists():
        ledger=read(ledger_path);existing={c['id']for c in ledger['claims']}
        require(not existing.intersection(c['id']for c in claims),'Binding IDs already exist; refusing duplicate additions')
    output.mkdir(parents=True);staged=output/tex_location;staged.parent.mkdir(parents=True);staged.write_text(tex,encoding='utf-8',newline='\n')
    additions=dict(schema='staged_manuscript_bindings_v1',operation='append_only_after_source_installation_and_review',
        source_sha256=pins[paths['summary']],target_tex_location=tex_location,claims=claims)
    (output/'claims.additions.json').write_text(json.dumps(additions,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    receipt=dict(schema='joint_publication_formatting_v1',passed=True,staging_only=True,manuscript_installed=False,ledger_modified=False,
        counts=COUNTS,score_table_rows=20,diagnostic_table_rows=20,floor_census_table_rows=20,claim_bindings=len(claims),source_pins=pins,
        formatter_sha256=sha(__file__),staged_tex_sha256=sha(staged),claims_sha256=sha(output/'claims.additions.json'),
        scientific_calls=0,scope='Formatting and exact-pointer staging after completed acceptance; no new scientific calculation or claim promotion.')
    (output/'render_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    for name in ('summary','result','index','audit','completion-review'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--tex-location',default='chapters/13_s04b_joint_nuisance.tex')
    args=parser.parse_args();paths={k:getattr(args,k)for k in ('summary','result','index','audit','completion_review')}
    print(json.dumps(stage(args.repository,paths,args.output,args.tex_location),indent=2))
