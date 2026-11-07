"""Extend metadata custody using accepted saved rows only; no scientific evaluation."""
import argparse
import ast
from collections import Counter
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile
import numpy as np


def require(value,message):
    if not value: raise ValueError(message)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def run(root,output,public_folder):
    sys.path.insert(0,str(root))
    from reproduction.score_replay import coverage_report as coverage
    base=root/'reproduction/score_replay';publication=root/'validation/reproductions/score_replay_20261107'
    checkpoint=publication/'table_metadata';pins={};archives={};accepted={};registries={};used_rows={};operands={}
    def raw(path):
        data=path.read_bytes();pins[path.relative_to(root).as_posix()]=digest(data);return data
    def load(path):return json.loads(raw(path))
    def archive_hash(path):
        if path not in archives:archives[path]=digest(path.read_bytes())
        return archives[path]
    def resource(path,member,data):
        return dict(archive=path.relative_to(root).as_posix(),archive_sha256=archive_hash(path),member=member,sha256=digest(data))
    def input_member(folder,spec):
        path=folder/spec['archive']
        with zipfile.ZipFile(path)as z:
            require(z.namelist().count(spec['member'])==1,'Duplicate/missing original input')
            data=z.read(spec['member'])
        require(digest(data)==spec['sha256'],'Original input member changed')
        return data,resource(path,spec['member'],data)
    def operand(spec,pointer,value):
        key=digest(json.dumps(dict(resource=spec,pointer=pointer),sort_keys=True).encode())
        operands[key]=dict(resource=spec,pointer=pointer,value=value);return key
    original=load(checkpoint/'metadata_crosswalk.json');original_evidence=load(checkpoint/'evidence.json')
    require(len(original['entries'])==56 and len(original['unresolved'])==63,'Original checkpoint scope differs')
    require(original_evidence['producer_sha256']==digest(raw(checkpoint/'producer.py')),'Original producer identity changed')
    original_evidence_sha=pins[(checkpoint/'evidence.json').relative_to(root).as_posix()]
    require(all(e['evidence']['resource']['sha256']==original_evidence_sha for e in original['entries']),
            'Original crosswalk/evidence identity changed')
    inventory={t['id']:t for t in load(base/'table_inventory.json')['tables']}
    raw(base/'coverage_report.py');raw(base/'inventory.py')
    for tid in sorted({x['table_id']for x in original['unresolved']}):
        t=inventory[tid];parsed=coverage.parse_tables(raw(root/t['source_file']).decode())[int(tid.rsplit(':',1)[1])-1]
        require(parsed['body_sha256']==t['body_sha256'],'Table source changed')
    index=load(publication/'accepted_execution_index.json')
    allowed={'california','s06_ca','california_blocks','original_li','observed_fixedbackbone'}
    for name in sorted(allowed):
        path=base/name/'registry.json';reg=load(path)
        for i,row in enumerate(reg['rows']):registries[row['id']]=(row,path,i)
    def admit(archive,review_path,result_pin,accepted_ids=None,archive_pin=None):
        reviewed=load(review_path);review_sha=pins[review_path.relative_to(root).as_posix()]
        require(reviewed.get('passed')is True or reviewed.get('status')in
            ('passed_independent_output_review','passed_independent_complete_registry_output_audit'),'Output review did not pass')
        expected_archive=archive_pin if archive_pin is not None else reviewed['artifact_sha256']
        require(archive_hash(archive)==expected_archive,'Review/index archive mismatch')
        with zipfile.ZipFile(archive)as z:
            require(len(z.namelist())==len(set(z.namelist())),'Duplicate execution member')
            raw_result=z.read('science/result.json');require(digest(raw_result)==result_pin,'Execution result identity differs')
            result=json.loads(raw_result)
            if accepted_ids is None:require(result['passed']is True,'Unaccepted failed execution')
            else:require(result['passed']is False,'Partial-row review must preserve failed original pilot')
            found=set()
            for entry in result['rows']:
                if accepted_ids is not None and entry['id']not in accepted_ids:continue
                require(entry['passed']is True,'Indexed row did not pass')
                name='science/'+entry['result'];data=z.read(name);report=json.loads(data)
                require(digest(data)==entry['sha256'] and report.get('passed')is True and
                    report.get('status')=='replayed' and report['id']==entry['id'],'Row result identity/status differs')
                found.add(report['id']);proof=dict(resource=resource(archive,name,data),review=dict(
                    path=review_path.relative_to(root).as_posix(),sha256=review_sha),original_execution_passed=result['passed'])
                if report['id']in accepted:
                    require(accepted[report['id']][1]['resource']['sha256']==digest(data),'Conflicting accepted row')
                else:accepted[report['id']]=(report,proof)
            if accepted_ids is not None:require(found==accepted_ids,'Partial accepted row roster differs')
    for entry in index['entries']:
        if entry['route']not in allowed:continue
        require(entry['passed']is True,'Unaccepted index entry')
        archive=root/entry['archive'];review_path=root/entry['review_path']
        require(archive_hash(archive)==entry['archive_sha256'] and digest(raw(review_path))==entry['review_sha256'],
                'Accepted index evidence changed')
        admit(archive,review_path,entry['science_result_sha256'],archive_pin=entry['archive_sha256'])
    # Individually reviewed pilot rows are usable metadata evidence even when
    # the complete route is still pending; full-route acceptance is never inferred.
    blocks=publication/'california_blocks'
    for phase in ('pilot','completion'):
        review_path=blocks/(phase+'_independent_review.json');archive=blocks/(phase+'.zip')
        if review_path.is_file() and archive.is_file():
            reviewed=load(review_path);admit(archive,review_path,reviewed['result_sha256'])
    li=publication/'original_li';partial=li/'partial_pilot_independent_review.json'
    if partial.is_file():
        reviewed=load(partial)
        require(reviewed.get('original_pilot_passed')is False and reviewed['accepted_rows']==2,'Partial LI scope changed')
        admit(li/'failed_pilot01.zip',partial,reviewed['result_sha256'],{r['id']for r in reviewed['retained_passed_rows']})
    def proof(identity):
        require(identity in accepted,'No accepted actual row: '+identity)
        report,evidence=accepted[identity];row,path,position=registries[identity]
        entry=dict(evidence,registry=dict(path=path.relative_to(root).as_posix(),sha256=pins[path.relative_to(root).as_posix()],pointer=f'/rows/{position}'))
        used_rows[identity]=entry;return report,row,path.parent
    def state(identity):
        report,row,folder=proof(identity);spec=row.get('state',row.get('selected_states'))
        data,source=input_member(folder,spec)
        actual_hash=report.get('state_sha256',report.get('actual',{}).get('state_sha256'))
        require(actual_hash==spec['sha256'],'Accepted selected-state identity differs')
        return json.loads(data),source
    geometry=load(base/'s06_ca/registry.json')['rows'][0]['geometry'];data,geometry_resource=input_member(base/'s06_ca',geometry)
    tree=ast.parse(data.decode());profiles=next(n.value for n in tree.body if isinstance(n,ast.Assign)and
        any(isinstance(t,ast.Name)and t.id=='PROFILES'for t in n.targets))
    profile=next(v for k,v in zip(profiles.keys,profiles.values)if ast.literal_eval(k)=='california')
    epoch_text=ast.literal_eval(next(k.value for k in profile.keywords if k.arg=='epoch'))
    epoch=dt.datetime.fromisoformat(epoch_text.replace('Z','+00:00'))
    clock_operand=operand(geometry_resource,'AST:PROFILES/california/epoch',epoch_text)
    def year(days):return (epoch+dt.timedelta(days=float(days))).year
    annual_years={}
    def annual(group):
        if group in annual_years:return annual_years[group]
        rows=load(base/'california_blocks/registry.json')['rows'];basis=[clock_operand];windows=set()
        for row in rows:
            if row['group']!=group:continue
            support=row['support_row_id'];report,original,folder=proof(support)
            require(report['actual']['cache_sha256']==original['cache']['sha256'],'Cohort cache differs')
            data,spec=input_member(folder,original['cache'])
            with np.load(io.BytesIO(data),allow_pickle=False)as saved:metadata=json.loads(str(saved['metadata_json']))
            geometry_pins=[v for k,v in metadata['production_source_pins'].items()if k.replace('\\','/').endswith('/geometry.py')]
            require(geometry_pins==[geometry['sha256']],'Cohort calendar constructor differs')
            windows.add((year(metadata['start']),year(metadata['end'])))
            basis.extend(operand(dict(spec,array='metadata_json'),'/'+key,metadata[key])for key in ('start','end'))
        require(windows,'Missing original calendar cohorts')
        years=sorted({y for start,end in windows for y in range(start,end)})
        require(len(years)==15 and years==list(range(years[0],years[-1]+1)),'Calendar cohort span is not contiguous')
        annual_years[group]=(years,basis);return years,basis
    records=[];entries=[];unresolved=[]
    for item in original['unresolved']:
        tid=item['table_id'];r=item['source_row_index'];c=item['column_index'];token=item['numeric_token_index']
        candidates=item['required_scored_record_ids'];support=[];basis=[];value=None;role=None;rule=None
        if tid.startswith('11_s06_completed:table:'):
            if not all(x in accepted for x in candidates):
                unresolved.append(dict(item,reason='Required S06 episode rows are not all accepted'));continue
            values=[]
            for identity in candidates:
                data,spec=state(identity);report,row,_=proof(identity)
                require(row['geometry']['sha256']==geometry['sha256'] and
                        report['actual']['catalogue_sha256']==row['catalogue']['sha256'],'Episode clock/raw cohort identity differs')
                values.append(year(data['start']));basis.append(operand(spec,'/start',data['start']))
            require(len(set(values))==1,'Episode origin years disagree across evaluated arms/partitions')
            value=values[0];basis.append(clock_operand);support=candidates;role='episode_origin_year'
            rule='Year of the exact saved state start under its pinned original California epoch; every required actual arm/partition state agrees.'
        elif tid=='13_continuous_local_inhibition:table:6':
            if not all(x in accepted for x in candidates):
                unresolved.append(dict(item,reason='Both original LI/OC seed rows have not been independently accepted'));continue
            values=[]
            for identity in candidates:
                data,spec=state(identity);report,row,_=proof(identity)
                require(data['case']==row['case'] and report['actual']['raw_sha256']==row['raw']['sha256'],'Seed case/raw identity differs')
                match=re.fullmatch(r'S\d+_.+_seed(\d+)',data['case']);require(match is not None,'Missing original seed identity')
                values.append(int(match[1]));basis.append(operand(spec,'/case',data['case']))
            require(len(set(values))==1,'Original selected LI/OC states have different seeds')
            value=values[0];support=candidates;role='seed';rule='Seed suffix of the original selected-state case, matching accepted LI/OC row and raw-input identities.'
        elif tid=='13_s04_observed_completed:table:1':
            if not all(x in accepted for x in candidates):
                unresolved.append(dict(item,reason='Required observed selected-state replay has not been accepted'));continue
            values=[]
            for identity in candidates:
                data,spec=state(identity);report,row,_=proof(identity)
                require(data['case']==row['case'] and report['prepared_sha256']==row['prepared']['sha256'],'Observed case/preparation differs')
                match=re.fullmatch(r'california_fold_(\d+)',data['case']);require(match is not None,'Missing original fold identity')
                values.append(int(match[1]));basis.append(operand(spec,'/case',data['case']))
            require(len(set(values))==1,'Observed fold identities disagree')
            value=values[0];support=candidates;role='fold_id';rule='Fold number in the exact selected-state case evaluated on its accepted prepared input.'
        elif tid in ('ch11_backup:table:3','ch11_backup:table:8'):
            group='primary_annual'if tid.endswith(':3')else'm45_annual';years,clock_basis=annual(group)
            require(c==0 and token==0 and 0<=r-2<len(years),'Unexpected annual metadata position')
            intended=years[r-2];values=[];basis=list(clock_basis)
            for identity in sorted(accepted):
                if not identity.startswith(group+'/'):continue
                report,row,_=proof(identity)
                source_report,source_row,_=proof(row['fresh_score_row_id'])
                require(report['actual']['fresh_dependency']['source_row_id']==row['fresh_score_row_id'] and
                        report['actual']['state_sha256']==source_row['state']['sha256'] and
                        report['actual']['cache_sha256']==source_row['cache']['sha256'],
                        'Annual row differs from its accepted selected state/cache')
                for position,actual in enumerate(report['actual']['rows']):
                    start=dt.datetime.fromisoformat(actual['start_utc'].replace('Z','+00:00'))
                    if start.year!=intended:continue
                    end=dt.datetime.fromisoformat(actual['end_utc'].replace('Z','+00:00'))
                    require(actual['status']=='succeeded' and start.month==start.day==1 and end.year==start.year+1 and
                        end.month==end.day==1 and actual['fold_id']==row['fold'],'Actual annual interval identity differs')
                    values.append(start.year);support.append(identity)
                    basis.append(operand(used_rows[identity]['resource'],f'/actual/rows/{position}/start_utc',actual['start_utc']))
            if not values:
                unresolved.append(dict(item,reason='No accepted annual interval row for this original cohort calendar position'));continue
            require(len(set(values))==1,'Actual annual labels disagree');value=values[0];role='calendar_year'
            rule='Chronological calendar position in the original accepted full-cohort cache span, verified against an actual accepted annual-compensator row start; whole-fold score agreement is not used as interval evidence.'
        else:raise ValueError('Unknown unresolved metadata field: '+item['identity'])
        # Display values are comparison targets only, after deriving the source value.
        literal,display,_=coverage.source_number(inventory[tid],r,c,token)
        require(value==display,'Derived metadata differs from display: '+item['identity'])
        record=dict(id=item['identity'],passed=True,role=role,value=value,derivation=rule,
                    supporting_accepted_rows=sorted(set(support)),metadata_operand_keys=sorted(set(basis)),source_display=literal,comparison_only=True)
        position=len(records);records.append(record)
        entries.append({**{k:v for k,v in item.items()if k not in ('identity','status','reason','required_scored_record_ids')},
            'role':role,'evidence':dict(resource=dict(path=public_folder+'/evidence.json',sha256=None),
                record_pointer=f'/records/{position}',identity_pointer='/id',identity=item['identity'],value_pointer='/value')})
    require(len(records)+len(unresolved)==63,'Metadata extension census changed')
    evidence=dict(schema='score_table_metadata_extension_v1',passed=True,all_metadata_complete=not unresolved,
        scope='Additional identity metadata from individually accepted rows only; no likelihood replay, fit or independent scientific acceptance.',
        producer_sha256=digest(Path(__file__).read_bytes()),predecessor_evidence_sha256=original_evidence_sha,
        source_pins=pins,accepted_rows=used_rows,metadata_operands=operands,records=records,unresolved=unresolved)
    output.mkdir(parents=True,exist_ok=False)
    (output/'evidence.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    evidence_sha=digest((output/'evidence.json').read_bytes())
    for entry in entries:entry['evidence']['resource']['sha256']=evidence_sha
    document=dict(schema='score_table_metadata_dispositions_v1',scope='Preserved original56 plus source-derived accepted metadata extension; unexecuted fields remain unresolved.',
        entries=original['entries']+entries,unresolved=unresolved)
    (output/'metadata_crosswalk.json').write_text(json.dumps(document,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    result=dict(passed=True,original_checked_fields=56,new_checked_fields=len(records),total_checked_fields=56+len(records),
        unresolved_fields=len(unresolved),new_checked_tables=dict(Counter(x['table_id']for x in entries)),
        unresolved_tables=dict(Counter(x['table_id']for x in unresolved)),evidence_sha256=evidence_sha,
        crosswalk_sha256=digest((output/'metadata_crosswalk.json').read_bytes()),scientific_calls=0,
        original_snapshot_preserved=True,independent_review_pending=True)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-folder',default='validation/reproductions/score_replay_20261107/table_metadata/extension_01')
    args=parser.parse_args();run(args.repository.resolve(),args.output.resolve(),args.public_folder)
