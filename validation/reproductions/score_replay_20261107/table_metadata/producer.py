"""Metadata-only relations from accepted rows; no model/native computation."""
import argparse,ast,datetime as dt,hashlib,io,json,re,sys,zipfile
from collections import Counter
from pathlib import Path
import numpy as np

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def refs(value):
 if isinstance(value,dict):
  for key,item in value.items():
   if key in ('row','record','d_row','w_row','train_row') and isinstance(item,str):yield item
   else:yield from refs(item)
 elif isinstance(value,list):
  for item in value:yield from refs(item)
def write_new(path,value):
 require(not path.exists(),'Output already exists: '+str(path))
 path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def run(root,output):
 sys.path.insert(0,str(root))
 from reproduction.score_replay import coverage_report as c
 base=root/'reproduction/score_replay';pub=root/'validation/reproductions/score_replay_20261107'
 public_folder='validation/reproductions/score_replay_20261107/table_metadata'
 pins={};archive_pins={};used_rows={};registry_rows={};cache_meta={};states={};used_values={}
 def read(path):
  raw=path.read_bytes();pins[path.relative_to(root).as_posix()]=sha(raw);return raw
 def load(path):return json.loads(read(path))
 def archive(path):
  if path not in archive_pins:archive_pins[path]=sha(path.read_bytes())
  return archive_pins[path]
 def member(spec,folder):
  path=folder/spec['archive'];data=None
  with zipfile.ZipFile(path) as z:
   require(z.namelist().count(spec['member'])==1,'Missing/duplicate resource member')
   data=z.read(spec['member'])
  require(sha(data)==spec['sha256'],'Input member SHA differs')
  resource=dict(archive=path.relative_to(root).as_posix(),archive_sha256=archive(path),member=spec['member'],sha256=spec['sha256'])
  return data,resource
 read(base/'coverage_report.py');read(base/'inventory.py')
 require([c.source_number(dict(source_rows=['X & [2011,2016)']),0,1,i)[1] for i in (0,1)]==[2011.,2016.],'Shared calendar tokenizer dependency is not corrected')
 inventory={t['id']:t for t in load(base/'table_inventory.json')['tables']}
 plan={t['table_id']:t for t in load(base/'coverage_plan.json')['table_dependencies']}
 mapped={tid:[] for tid in inventory};covered={tid:set() for tid in inventory}
 for filename in ('table_links_cached.json','table_links_regional.json'):
  for table in load(base/filename)['tables']:
   tid=table['id'];require(table['source_file']==inventory[tid]['source_file'],'Mapping source differs')
   for cell in table['cells']:
    if cell.get('expression') is None:continue
    mapped[tid].append(cell);covered[tid].add(c.field_key(cell))
    row=cell['source_row_index'];col=cell['column_index'];raw=re.split(r'\\',inventory[tid]['source_rows'][row].split('&')[col])[0].strip()
    if cell.get('display_type')=='profile_support_list':
     covered[tid].update(k for k in c.inventory_numeric_fields(inventory[tid]) if k.startswith(f'{row}:{col}:'))
    if cell['expression'].get('op')=='wins' and re.fullmatch(r'\d+\s*/\s*\d+',raw):covered[tid].add(f'{row}:{col}:1')
 for kind in ('initial_mark','s02'):
  bindings,contracts=c.case_bindings(kind)
  for tid,label,ptr,row,col,tok in bindings:covered[tid].add(f'{row}:{col}:{tok}')
  for tid,row,col,tok,value,scope in contracts:covered[tid].add(f'{row}:{col}:{tok}')
 needed=[]
 for tid,table in inventory.items():
  if plan[tid]['execution_status'] in ('already_replayed','no_likelihood_evaluation_required'):continue
  actual=c.parse_tables(read(root/table['source_file']).decode('utf-8'))[int(tid.rsplit(':',1)[1])-1]
  require(actual['body_sha256']==table['body_sha256'],'Current table body differs')
  for field in sorted(c.inventory_numeric_fields(table)-covered[tid]):
   row,col,tok=map(int,field.split(':'));literal,display,half=c.source_number(table,row,col,tok)
   needed.append(dict(table_id=tid,source_body_sha256=table['body_sha256'],source_row_index=row,column_index=col,numeric_token_index=tok,source_token=literal))
 require(len(needed)==119,'Unexpected source metadata census')
 accepted_index=load(pub/'accepted_execution_index.json');accepted={};acceptance_entries=[]
 # Freeze this assignment's eligible completed routes. Later arrivals do not
 # silently complete S06/blocks/LI/S04/observed metadata in this checkpoint.
 allowed={'california','jma','s03'}
 for entry in accepted_index['entries']:
  if entry['route'] not in allowed:continue
  require(entry.get('passed') is True,'Unaccepted execution index entry')
  path=root/entry['archive'];require(archive(path)==entry['archive_sha256'],'Accepted archive SHA differs')
  review_raw=read(root/entry['review_path']);require(sha(review_raw)==entry['review_sha256'],'Review identity differs')
  review=json.loads(review_raw)
  require(review.get('passed') is True or review.get('status') in ('passed_independent_output_review','passed_independent_complete_registry_output_audit'),'Review did not pass')
  result_member=entry.get('science_result_member','science/result.json')
  with zipfile.ZipFile(path) as z:
   raw=z.read(result_member);require(sha(raw)==entry['science_result_sha256'],'Science result pin differs');result=json.loads(raw)
   require(result.get('passed') is True,'Execution did not pass')
   for indexed in result['rows']:
    require(indexed['passed'] is True,'Indexed row did not pass')
    name=(Path(result_member).parent/ indexed['result']).as_posix();raw=z.read(name)
    require(sha(raw)==indexed['sha256'],'Row result SHA differs');value=json.loads(raw)
    require(value.get('passed') is True and value.get('status')=='replayed' and value['id']==indexed['id'],'Actual row failed or identity changed')
    require(value['id'] not in accepted,'Duplicate accepted metadata source row')
    spec=dict(archive=entry['archive'],archive_sha256=entry['archive_sha256'],member=name,sha256=sha(raw))
    accepted[value['id']]=(value,spec,entry)
  acceptance_entries.append(entry)
 for folder in sorted(allowed):
  registry_path=base/folder/'registry.json';registry=load(registry_path)
  for i,row in enumerate(registry['rows']):registry_rows[row['id']]=(row,registry_path,i)
 def proof(identity):
  require(identity in accepted,'No accepted execution: '+identity)
  report,spec,entry=accepted[identity];row,registry_path,i=registry_rows[identity]
  require(report['actual']['state_sha256']==row['state']['sha256'],'Accepted fitted state differs')
  if 'cache' in row:require(report['actual']['cache_sha256']==row['cache']['sha256'],'Accepted input cache differs')
  used_rows[identity]=dict(resource=spec,record_identity_pointer='/id',passed_pointer='/passed',status_pointer='/status',registry=dict(path=registry_path.relative_to(root).as_posix(),sha256=pins[registry_path.relative_to(root).as_posix()],pointer=f'/rows/{i}'),review=dict(path=entry['review_path'],sha256=entry['review_sha256']))
  return report,row,registry_path.parent
 def state(identity):
  if identity not in states:
   _,row,folder=proof(identity);raw,spec=member(row['state'],folder);states[identity]=(json.loads(raw),spec)
  return states[identity]
 def metadata(identity):
  if identity not in cache_meta:
   _,row,folder=proof(identity);raw,spec=member(row['cache'],folder)
   with np.load(io.BytesIO(raw),allow_pickle=False) as z:value=json.loads(str(z['metadata_json']))
   cache_meta[identity]=(value,dict(spec,array='metadata_json'))
  return cache_meta[identity]
 def record_value(spec,pointer,value):
  key=sha(json.dumps(dict(resource=spec,pointer=pointer),sort_keys=True).encode())
  used_values[key]=dict(resource=spec,pointer=pointer,value=value);return key
 # Derive the source clocks from the exact packaged constructors, not dates
 # transcribed from the manuscript table labels.
 geometry_registry=load(base/'s06_ca/registry.json');geometry_ref=geometry_registry['rows'][0]['geometry']
 raw,geometry_spec=member(geometry_ref,base/'s06_ca');tree=ast.parse(raw.decode())
 profiles=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROFILES' for t in n.targets))
 profile=next(v for k,v in zip(profiles.keys,profiles.values) if ast.literal_eval(k)=='california')
 ca_epoch=dt.datetime.fromisoformat(ast.literal_eval(next(k.value for k in profile.keywords if k.arg=='epoch')).replace('Z','+00:00'))
 runner_path=root/'reproduction/regional/payload.zip'
 with zipfile.ZipFile(runner_path) as z:runner_raw=z.read('S06/source/s06/runner.py')
 runner_spec=dict(archive=runner_path.relative_to(root).as_posix(),archive_sha256=archive(runner_path),member='S06/source/s06/runner.py',sha256=sha(runner_raw))
 function=next(n for n in ast.parse(runner_raw.decode()).body if isinstance(n,ast.FunctionDef) and n.name=='annual_intervals')
 epoch_call=next(n.value for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='epoch' for t in n.targets))
 require(isinstance(epoch_call.func,ast.Name) and epoch_call.func.id=='datetime','Unexpected source-year clock constructor')
 jma_epoch=dt.datetime(*(ast.literal_eval(x) for x in epoch_call.args),tzinfo=dt.timezone.utc)
 def calendar_year(epoch,days):return (epoch+dt.timedelta(days=float(days))).year
 def cached_interval(identity):
  report,row,_=proof(identity);value,spec=metadata(identity)
  geometry_pins=[v for k,v in value['production_source_pins'].items() if k.replace('\\','/').endswith('/geometry.py')]
  require(geometry_pins==[geometry_ref['sha256']],'Cache geometry/epoch constructor identity differs')
  basis=[record_value(spec,'/start',value['start']),record_value(spec,'/end',value['end']),record_value(used_rows[identity]['resource'],'/actual/components/n_events',report['actual']['components']['n_events'])]
  return (calendar_year(ca_epoch,value['start']),calendar_year(ca_epoch,value['end']),report['actual']['components']['n_events']),basis
 def fold(identity):
  report,row,path=proof(identity);match=re.fullmatch(r'(?:california|JMA|CA|NZ)_fold_(\d+)',row['case'])
  require(match is not None and identity.split('/')[1]==row['case'],'Case identity is not a declared fold')
  registry_spec=used_rows[identity]['registry']
  basis=record_value({k:v for k,v in registry_spec.items() if k!='pointer'},registry_spec['pointer']+'/case',row['case'])
  return int(match[1]),basis
 def signed_arms(expression,scale=1):
  op=expression['op']
  if op=='sum':return sum((signed_arms(x,scale) for x in expression['terms']),[])
  if op=='scale':
   require(expression['weight'] in (-1,1),'Unexpected arm contrast coefficient');return signed_arms(expression['value'],scale*expression['weight'])
  require(op=='field' and expression['pointer']=='/actual/components/joint','Header is not an actual joint-score arm contrast')
  identity=expression['record'];value,spec=state(identity);arm=value['arm'];require(arm in (1,2,3,4),'Unknown S03 arm')
  return [(scale*arm,identity,record_value(spec,'/arm',arm))]
 records=[];crosswalk=[];unresolved=[]
 future=('11_s06_completed:table:1','11_s06_completed:table:2','13_continuous_local_inhibition:table:6','13_s04_observed_completed:table:1','ch11_backup:table:3','ch11_backup:table:8')
 for item in needed:
  tid=item['table_id'];r=item['source_row_index'];col=item['column_index'];token=item['numeric_token_index'];identity=f'{tid}/{r}:{col}:{token}'
  candidates=sorted(set(x for cell in mapped[tid] if cell['source_row_index']==r for x in refs(cell['expression'])))
  if tid in future:
   unresolved.append(dict(item,identity=identity,status='not_run',reason='Required route is outside the accepted completed-route snapshot for this assignment',required_scored_record_ids=candidates));continue
  basis=[];role=None;value=None;rule=None;support=candidates
  if tid in ('11_external_transfer_benchmarks:table:2','ch11_backup:table:2','ch11_backup:table:6'):
   require(col==0 and candidates,'Unexpected CA interval metadata field')
   intervals=[]
   for candidate in candidates:
    numbers,keys=cached_interval(candidate);intervals.append(numbers);basis+=keys
   require(len(set(intervals))==1,'Accepted procedures have different interval/cohort identities')
   value=intervals[0][token];role='count' if token==2 else 'interval_endpoint'
   rule='Calendar years of the exact evaluated cache start/end under its hash-bound original California epoch; target count from the actual evaluated components.'
  elif tid=='11_external_transfer_benchmarks:table:6':
   require(len(candidates)==1,'Unexpected JMA interval row');data,spec=state(candidates[0])
   selectors={(0,0):('/start',data['start'],0),(1,0):('/nuisance/training_start',data['nuisance']['training_start'],0),(1,1):('/nuisance/training_end',data['nuisance']['training_end'],-1),(3,0):('/start',data['start'],0),(3,1):('/end',data['end'],-1)}
   pointer,days,inclusive=selectors[col,token];basis=[record_value(spec,pointer,days)]
   value=calendar_year(jma_epoch,days)+inclusive;role='year';rule='Original source-JST calendar-year clock from annual_intervals; exclusive end boundaries converted to the last included calendar year.'
  elif tid=='11_s03_completed:table:1' and r==0:
   patterns=[];support=[]
   for cell in mapped[tid]:
    if cell['column_index']!=col:continue
    derived=signed_arms(cell['expression']);patterns.append(tuple(x[0] for x in derived));support += [x[1] for x in derived];basis += [x[2] for x in derived]
   require(patterns and len(set(patterns))==1,'Contrast header has inconsistent evaluated arm identities')
   value=patterns[0][token];role='contrast_arm_label';rule='Signed original arm identifiers in every accepted data-row joint-score contrast underneath this column; no score value is used.'
  elif tid in ('11_s03_completed:table:1','11_s06_completed:table:3'):
   require(candidates,'Missing scored fold identities');derived=[fold(x) for x in candidates];values={x[0] for x in derived};require(len(values)==1,'Mixed fold identities');basis=[x[1] for x in derived]
   value=next(iter(values));role='fold_id';rule='Fold identifier parsed from exact registry case IDs equal to accepted execution row IDs; no printed fold value is an operand.'
  else:raise ValueError('No explicit metadata rule: '+identity)
  support=sorted(set(support));require(all(x in accepted for x in support),'Metadata depends on an unaccepted row')
  # Only after deriving the value do we compare it with the source display.
  source_literal,display,_=c.source_number(inventory[tid],r,col,token)
  passed=value==display
  index=len(records);records.append(dict(id=identity,passed=passed,role=role,value=value,derivation=rule,supporting_accepted_rows=support,metadata_operand_keys=sorted(set(basis)),source_display=source_literal,comparison_only=True))
  crosswalk.append(dict(item,role=role,evidence=dict(resource=dict(path=public_folder+'/evidence.json',sha256=None),record_pointer=f'/records/{index}',identity_pointer='/id',identity=identity,value_pointer='/value')))
 require(len(records)==56 and len(unresolved)==63,'Unexpected checkpoint scope')
 require(all(x['passed'] for x in records),'Derived metadata/source display mismatch: '+json.dumps([x for x in records if not x['passed']]))
 evidence=dict(schema='score_table_metadata_evidence_v1',passed=True,all_metadata_complete=False,scope='Identity/count metadata only from the declared accepted-row snapshot. This is not a likelihood replay or independent scientific acceptance.',producer_sha256=sha(Path(__file__).read_bytes()),source_pins=pins,accepted_route_scope=sorted(allowed),accepted_index_entries_used=acceptance_entries,clock_sources=dict(california=dict(resource=geometry_spec,selector='PROFILES[california].epoch',epoch=ca_epoch.isoformat()),jma=dict(resource=runner_spec,selector='annual_intervals/epoch',source_year_clock_epoch=jma_epoch.isoformat())),accepted_rows=used_rows,metadata_operands=used_values,records=records,unresolved=unresolved)
 write_new(output/'evidence.json',evidence);evidence_hash=sha((output/'evidence.json').read_bytes())
 for item in crosswalk:item['evidence']['resource']['sha256']=evidence_hash
 document=dict(schema='score_table_metadata_dispositions_v1',scope='56 checked metadata source tokens; 63 explicitly unresolved. Publish only after conductor review; no existing repo file has been changed.',entries=crosswalk,unresolved=unresolved)
 write_new(output/'metadata_crosswalk.json',document)
 prior=(output/'result.json').read_bytes() if (output/'result.json').exists() else None
 result=dict(task='coverage_metadata_evidence',attempt='dbf3df1b-899a-4ba0-a815-172df011f61c',implementation_complete=True,independent_review_pending=True,all_metadata_complete=False,source_metadata_tokens=119,checked_metadata_fields=len(records),unresolved_fields=len(unresolved),checked_tables=dict(Counter(x['table_id'] for x in crosswalk)),unresolved_tables=dict(Counter(x['table_id'] for x in unresolved)),accepted_rows_used=len(used_rows),source_sha256=sha(Path(__file__).read_bytes()),evidence_sha256=evidence_hash,crosswalk_sha256=sha((output/'metadata_crosswalk.json').read_bytes()),proposed_public_paths=[public_folder+'/evidence.json',public_folder+'/metadata_crosswalk.json'],scientific_calls=0,native_calls=0,fits=0,simulations=0,likelihood_calls=0,repository_edits=0,retained_prior_task_record=dict(sha256=sha(prior),exact_utf8_bytes=prior.decode('utf-8')) if prior else None)
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({k:result[k] for k in ('checked_metadata_fields','unresolved_fields','accepted_rows_used','evidence_sha256','crosswalk_sha256')}))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--repository',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args();run(args.repository.resolve(),args.output.resolve())
