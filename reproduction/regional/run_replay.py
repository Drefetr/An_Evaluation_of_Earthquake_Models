"""Bounded current S05 replay guard; archived numerical sources remain unchanged."""
import argparse,datetime as dt,hashlib,importlib.util,json,math,os,platform,subprocess,sys,time
from pathlib import Path
import psutil

MODES=('controls','pilot','probe_oc','probe_ep','full')
ORIGINS=tuple(f'california_fold_{i}' for i in range(3))
PROBES={'probe_oc':('OC',ORIGINS[0],74),'probe_ep':('EP',ORIGINS[2],573)}
CAPS={'controls':180,'pilot':180,'probe_oc':180,'probe_ep':180,'full_point':1800,'full_temporal':900}
TREE_CAP=8*1024**3;HEADROOM=4*1024**3;INITIAL_RESERVE=2*1024**3
FIELDS_POINT={'count','immigrant_exposure','trigger_exposure','exposure','time_event_logsum','timing_logscore','location_logscore','mark_logscore','joint_logscore'}
FIELDS_TEMPORAL=FIELDS_POINT-{'location_logscore','joint_logscore'}
POINT_COMPONENTS=('count','mark_sum','immigrant_exposure','trigger_exposure','event_log_ground','event_log_point','mark_logscore','joint_logscore')
def need(value,message):
 if not value:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return dt.datetime.now(dt.timezone.utc)
def stamp(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00'))
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def write(path,value):
 path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
 with temporary.open('w',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(temporary,path)
def identity(row):return row['model'],row['origin'],row['index']
def roster(mode):
 if mode in PROBES:return {PROBES[mode]}
 return {(m,o,i) for m in ('OC','EP') for o in ORIGINS for i in ([0] if mode=='pilot' else range(999))}
def archived_pins(binding):return {k:binding['sources'][k] for k in ('replay.py','original_full84.py','native_wrapper.py','independent.cpp','temporal_extension.cpp')}
def validate_rows(rows,mode,scope,receipts):
 expected=roster(mode);ids=[identity(r) for r in rows]
 need(len(ids)==len(set(ids)) and set(ids)==expected,'Missing, duplicate or unexpected replay identity')
 for row in rows:
  need(row.get('passed') is True and row.get('scope')==scope,'Failed row or wrong scope')
  need(finite(row.get('seconds')) and row['seconds']>=0,'Invalid row duration')
  metric=row.get('metrics',{});need(finite(metric.get('max_error')) and 0<=metric['max_error']<=1e-4,'Nonfinite or excessive score error')
  need(set(metric.get('recomputed_fields',[]))==(FIELDS_POINT if scope=='point' else FIELDS_TEMPORAL),'Score component coverage differs')
  need(metric.get('point_and_joint_recomputed') is (scope=='point'),'Point coverage flag differs')
  need(row.get('receipt_sha256')==receipts[identity(row)],'Current input receipt binding differs')
 return True
def validate_report(report,mode,scope,binding,receipts):
 need(report.get('passed') is True and report.get('failed')==0,'Child report is not successful')
 need(report.get('complete')==len(roster(mode)),'Incomplete child report')
 if mode not in PROBES:
  expected=dict(manifest_sha256=binding['manifest_sha256'],dll_sha256=binding['dll_sha256'],adapter_sha256=binding['sources']['replay.py'],source_pins=archived_pins(binding),scope=scope,pilot=mode=='pilot',planned=len(roster(mode)))
  need(report.get('binding')==expected,'Archived report binding differs')
 validate_rows(report['rows'],mode,scope,receipts)
def validate_controls(archived,point,binding):
 need(archived.get('passed') is True and archived.get('dll_sha256')==binding['dll_sha256'] and archived.get('source_sha256')==binding['sources']['replay.py'] and archived.get('source_pins')==archived_pins(binding),'Archived control binding/failure')
 need(archived.get('duplicate_timestamp_strictpast') is True,'Strict-past control missing')
 rows=archived.get('rows',[]);need(len(rows)==4 and {r['q'] for r in rows}=={1.05,1.4,2.,3.},'Archived control roster differs')
 for row in rows:
  for key in ('vector_error','detail_error','temporal_error'):need(finite(row.get(key)) and 0<=row[key]<=1e-7,'Archived control error')
 if binding['scope']=='temporal':return
 need(point is not None and point.get('passed') is True,'Native point controls missing/failed')
 need(point.get('wrapper_sha256')==binding['point_wrapper_sha256'] and point.get('library_sha256')==binding['dll_sha256'] and point.get('source_pins')==binding['sources'] and point.get('build_receipt_sha256')==binding['build_receipt_sha256'],'Native point control binding differs')
 expected={f'{m}_q{q}_{s}' for m,q in [('OC',2.)]+[('EP',q) for q in (1.05,1.4,2.,3.)] for s in ('empty_no_history','empty_with_prehistory','zero_branching_boundaries','strict_past','single_at_start')}
 cases=point.get('point_cases',[]);need(len(cases)==25 and {r['name'] for r in cases}==expected,'Point control roster differs')
 for row in cases:
  need(row.get('passed') is True and row.get('native_point_evaluate_called') is True and len(row.get('components',[]))==8,'Point control not executed/complete')
  for i,c in enumerate(row['components']):
   tol=0. if i==0 else 1e-12 if i==1 else 1e-7
   need(c.get('component')==POINT_COMPONENTS[i],'Point component identity differs')
   need(c.get('passed') is True and c.get('absolute_tolerance')==tol and finite(c.get('actual')) and finite(c.get('expected')) and finite(c.get('absolute_error')) and 0<=c['absolute_error']<=tol and abs(c['actual']-c['expected'])<=tol and abs(abs(c['actual']-c['expected'])-c['absolute_error'])<=1e-15,'Point component gate differs')
 geometry=point.get('geometry_cases',[]);need(len(geometry)==10 and len({r['name'] for r in geometry})==10,'Geometry control roster differs')
 expected_geo={(m,q,c) for m,q in [('OC',2.)]+[('EP',q) for q in (1.05,1.4,2.,3.)] for c in ((0.,0.),(3.-1e-8,1.))};need({(r['model'],r['q'],tuple(r['center'])) for r in geometry}==expected_geo,'Geometry identities differ')
 for row in geometry:
  need(row.get('passed') is True and row.get('absolute_tolerance')==1e-9 and len(row.get('absolute_error',[]))==len(row.get('actual',[]))==len(row.get('expected',[]))==9,'Geometry error/schema')
  for a,b,e in zip(row['actual'],row['expected'],row['absolute_error']):need(all(finite(v) for v in (a,b,e)) and 0<=e<=1e-9 and abs(a-b)<=1e-9 and abs(abs(a-b)-e)<=1e-15,'Geometry numerical discrepancy')
 need(bool(point.get('reference_integrals')),'Reference integral records missing')
 for r in point['reference_integrals']:need(r.get('passed') is True and finite(r.get('value')) and finite(r.get('estimated_absolute_error')) and 0<=r['estimated_absolute_error']<=1e-9,'Reference integral failure')
def live_identity(pid,created):
 try:
  process=psutil.Process(pid)
  return process if process.create_time()==created and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE else None
 except psutil.NoSuchProcess:return None
def supervise(command,folder,seconds,memory,environment,lease_check=lambda:None,minimum_available=HEADROOM):
 """Fail closed on supervision errors; clean only captured identities/owned handle."""
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);began=time.monotonic();started=now().isoformat()
 known={};peaks=0;cpu={};termination=None;actions=[];errors=[];primary_error=None;survivors=[];child=None;root=None;available_launch=None;available_min=None;discovery_uncertain=False;phase='initial_memory';grace_started=None;grace_elapsed=0.
 env=dict(environment);env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 def failure(exc,where):return dict(phase=where,error_type=type(exc).__name__,error=str(exc))
 def remember(p):
  try:known[(p.pid,p.create_time())]=p
  except psutil.NoSuchProcess:pass
 def discover():
  nonlocal discovery_uncertain
  try:
   for p in root.children(recursive=True) if root else ():remember(p)
  except psutil.NoSuchProcess:pass
  except BaseException:
   discovery_uncertain=True;raise
 try:
  available_launch=psutil.virtual_memory().available;available_min=available_launch
  phase='launch'
  with (folder/'stdout.log').open('w',encoding='utf-8') as out,(folder/'stderr.log').open('w',encoding='utf-8') as err:
   kwargs=dict(stdout=out,stderr=err,env=env)
   if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
   else:kwargs['start_new_session']=True
   child=subprocess.Popen(command,**kwargs);phase='root_identity'
   try:root=psutil.Process(child.pid);remember(root)
   except psutil.NoSuchProcess:root=None
   while True:
    root_exit=child.poll()
    if root_exit is not None and root_exit!=0:break
    if root_exit==0 and grace_started is None:grace_started=time.monotonic()
    phase='descendant_discovery';discover();rss=0;live_count=0
    for pid,created in list(known):
     phase='identity';p=live_identity(pid,created)
     if p is None:continue
     live_count+=1
     try:
      phase='memory_info';rss+=p.memory_info().rss;phase='cpu_times';t=p.cpu_times();cpu[(pid,created)]=t.user+t.system
     except psutil.NoSuchProcess:pass
    peaks=max(peaks,rss);phase='available_memory';available=psutil.virtual_memory().available;available_min=min(available_min,available)
    try:lease_check()
    except Exception as exc:termination='lease_lost: '+str(exc)
    if rss>memory:termination='memory_limit'
    if available<minimum_available:termination=termination or 'available_memory_headroom'
    if time.monotonic()-began>=seconds:termination=termination or 'wall_limit'
    if grace_started is not None:
     grace_elapsed=time.monotonic()-grace_started
     if live_count and grace_elapsed>=3.:termination=termination or 'lingering_owned_descendants'
    if termination:break
    if root_exit==0 and live_count==0:break
    pause=min(.1,max(0.,began+seconds-time.monotonic()))
    if grace_started is not None:pause=min(pause,max(0.,grace_started+3.-time.monotonic()))
    phase='sleep';time.sleep(pause)
 except BaseException as exc:
  primary_error=failure(exc,phase);termination=termination or 'supervision_exception'
  if phase=='root_identity':discovery_uncertain=True
 finally:
  # Every cleanup operation is isolated: one denied sample must not prevent
  # attempts on other captured identities or the exact Popen-owned root handle.
  if child is not None:
   try:discover()
   except BaseException as exc:errors.append(failure(exc,'cleanup_discovery'));termination=termination or 'cleanup_exception'
   remaining=[]
   for pid,created in list(known):
    try:
     p=live_identity(pid,created)
     if p is not None:remaining.append((pid,created,p))
    except BaseException as exc:errors.append(dict(pid=pid,create_time=created,**failure(exc,'cleanup_identity')));termination=termination or 'cleanup_exception'
   if remaining and child.poll() is not None:termination=termination or 'lingering_owned_descendants'
   if termination:
    for pid,created,p in reversed(remaining):
     action=dict(pid=pid,create_time=created,operation='kill',requested=False)
     try:
      exact=live_identity(pid,created)
      if exact is not None:exact.kill();action['requested']=True
      else:action['already_gone_or_identity_changed']=True
     except BaseException as exc:action.update(failure(exc,'cleanup_kill'));errors.append(dict(action))
     actions.append(action)
    # Popen retains ownership of this root (a process HANDLE on Windows).
    # This fallback never kills an arbitrary descendant using only a PID.
    try:
     if child.poll() is None:
      action=dict(pid=child.pid,operation='kill_owned_popen_handle',requested=False);actions.append(action)
      child.kill();action['requested']=True
    except BaseException as exc:errors.append(failure(exc,'cleanup_root_handle'))
    try:psutil.wait_procs([p for _,_,p in remaining],timeout=3)
    except BaseException as exc:errors.append(failure(exc,'cleanup_wait_procs'))
   try:child.wait(timeout=3)
   except BaseException as exc:errors.append(failure(exc,'cleanup_child_wait'));termination=termination or 'child_survived_termination'
   for pid,created in list(known):
    try:
     if live_identity(pid,created) is not None:survivors.append(dict(pid=pid,create_time=created,status='live'))
    except BaseException as exc:survivors.append(dict(pid=pid,create_time=created,status='unverified',**failure(exc,'survivor_identity')))
   if child.poll() is None and not any(r['pid']==child.pid for r in survivors):survivors.append(dict(pid=child.pid,status='live_owned_root'))
  if errors:termination=termination or 'cleanup_exception'
 result=dict(command=command,started_utc=started,finished_utc=now().isoformat(),exit_code=child.returncode if child else None,termination=termination,primary_error=primary_error,cleanup_errors=errors,descendant_discovery_uncertain=discovery_uncertain,normal_exit_grace_started=grace_started is not None,normal_exit_grace_limit_seconds=3.,normal_exit_grace_elapsed_seconds=grace_elapsed,elapsed_seconds=time.monotonic()-began,wall_limit_seconds=seconds,memory_limit_bytes=memory,available_memory_at_launch=available_launch,minimum_available_memory_bytes=available_min,required_headroom_bytes=minimum_available,peak_process_tree_rss_bytes=peaks,sampled_cpu_seconds=sum(cpu.values()),sampling_interval_seconds=.1,tracked=[dict(pid=p,create_time=c) for p,c in known],termination_actions=actions,survivors=survivors,passed=child is not None and child.returncode==0 and termination is None and not survivors and not discovery_uncertain)
 write(folder/'supervision.json',result);return result

def bindings(args,point):
 sources={name:sha(args.sources/name) for name in point.SOURCE_PINS};need(sources==point.SOURCE_PINS,'Archived source drift')
 return dict(scope=args.scope,wrapper_sha256=sha(__file__),point_wrapper_sha256=sha(args.point_controls),sources=sources,dll_sha256=sha(args.dll),manifest_sha256=sha(args.manifest),build_receipt_sha256=sha(args.build_receipt))
def lease_check(admission):
 lease=admission['lease'];need(sha(lease['snapshot_path'])==lease['snapshot_sha256'],'Lease snapshot changed');snapshot=read(lease['snapshot_path']);active=read(lease['active_path'])
 for row in (snapshot,active):
  need(row.get('status')=='active' and row.get('exclusive_numerical_slot') is True,'Numerical slot not active/exclusive')
  need(row.get('owner')==lease['owner'] and row.get('lease_id')==lease['lease_id'] and row.get('token_sha256')==lease['token_sha256'],'Numerical lease owner/identity changed')
  need(now()<stamp(row['expires_utc']),'Numerical lease expired')
 need(hashlib.sha256(os.environ.get('NUMERICAL_LEASE_TOKEN','').encode()).hexdigest()==lease['token_sha256'] and bool(os.environ.get('NUMERICAL_LEASE_TOKEN')),'Missing actual numerical lease token')
def materialized_receipts(manifest):
 d=read(manifest);need(d.get('passed') is True and len(d.get('rows',[]))==6000,'Materialized input manifest')
 ids=[identity(r) for r in d['rows']];need(len(set(ids))==6000 and set(ids)==roster('full')|{(m,o,-1) for m in ('OC','EP') for o in ORIGINS},'Input roster differs')
 return {identity(r):r['artifacts'][str(Path(r['scalars']).parent/'receipt.json')] for r in d['rows'] if r['index']>=0}
def import_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def probe_child(config_path):
 c=read(config_path);need(tuple(c['identity']) in PROBES.values(),'Undeclared probe');need(sha(c['admission'])==c['admission_sha256'],'Probe admission changed');admission=read(c['admission']);need(admission.get('status')=='admitted' and admission.get('mode') in PROBES and tuple(c['identity'])==PROBES[admission['mode']] and now()<stamp(admission['expires_utc']),'Probe phase admission differs/expired');lease_check(admission);b=c['binding'];need(c['scope']==b['scope'] and admission['binding']==b and sha(__file__)==b['wrapper_sha256'] and sha(c['dll'])==b['dll_sha256'] and sha(c['manifest'])==b['manifest_sha256'],'Probe source/input identity');need({k:sha(Path(c['sources'])/k) for k in b['sources']}==b['sources'],'Probe archived source drift');sys.path.insert(0,c['sources']);replay=import_module(Path(c['sources'])/'replay.py','_guard_probe_replay');replay.init(str(Path(c['dll']).resolve()));rows=replay.manifest(c['manifest'])['rows'];selected=[r for r in rows if identity(r)==tuple(c['identity'])];need(len(selected)==1,'Probe identity');row=replay.one((selected[0],c['scope']));report=dict(passed=row.get('passed') is True,complete=1,failed=int(row.get('passed') is not True),rows=[row]);write(Path(c['report']),report);return 0 if report['passed'] else 1
def evidence(path,expected_hash,binding):
 need(sha(path)==expected_hash,'Prior phase receipt changed');d=read(path);need(d.get('passed') is True and d.get('binding')==binding,'Prior phase failed or scope/inputs differ')
 for artifact in d['artifacts']:need(sha(artifact['path'])==artifact['sha256'],'Prior actual artifact changed')
 actual_paths={str(Path(a['path']).resolve()) for a in d['artifacts']}
 for key in ('score_report','archived_controls','point_controls'):
  if d.get(key):need(str(Path(d[key]).resolve()) in actual_paths,'Prior referenced report was not pinned')
 need(d.get('resources') and all(r.get('passed') is True and r.get('exit_code')==0 and r.get('termination') is None and not r.get('survivors') and finite(r.get('peak_process_tree_rss_bytes')) and r['peak_process_tree_rss_bytes']>0 and finite(r.get('elapsed_seconds')) for r in d['resources']),'Missing/failed actual resource measurements')
 return d
def projection(workload,phases,scope,workers,manifest_bytes):
 groups={(g['model'],g['origin']):g for g in workload['groups']};rates=[];rowtime=0.;elapsed=0.;peak=0
 for phase in phases:
  elapsed+=sum(x['elapsed_seconds'] for x in phase['resources']);peak=max(peak,max(x['peak_process_tree_rss_bytes'] for x in phase['resources']))
  for row in read(phase['score_report'])['rows']:
   g=groups[(row['model'],row['origin'])];N=g['pilot_events'] if row['index']==0 else g['maximum_events'];need(row['index']==0 or row['index']==g['maximum_index'],'Fixed workload probe identity differs');W=N*g['prehistory']+N*(N-1)/2+N+(N*(g['training']+9) if scope=='point' else 0);rates.append(row['seconds']/W);rowtime+=row['seconds']
 total=sum(g['temporal_parent_pairs']+g['sum_events']+(g['sum_events']*(g['training']+9) if scope=='point' else 0) for g in groups.values());maximum=max(g['maximum_events']*g['prehistory']+g['maximum_events']*(g['maximum_events']-1)/2+g['maximum_events']+(g['maximum_events']*(g['training']+9) if scope=='point' else 0) for g in groups.values());rate=max(rates);startup=max(30.,elapsed-rowtime)
 return dict(projected_seconds=3*max(rate*total/workers,rate*maximum)+workers*startup,projected_tree_bytes=math.ceil(1.5*workers*peak)+max(128*1024**2,16*manifest_bytes),os_headroom_bytes=HEADROOM,max_seconds_per_work_unit=rate,work_units=total,startup_allowance_seconds=workers*startup)
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--child-probe',type=Path);p.add_argument('--mode',choices=MODES);p.add_argument('--scope',choices=('point','temporal'),default='point')
 for name in ('sources','dll','manifest','point-controls','build-receipt','admission','output'):p.add_argument('--'+name,type=Path)
 args=p.parse_args(argv)
 if args.child_probe:return probe_child(args.child_probe)
 need(args.mode and all(getattr(args,k) for k in ('sources','dll','manifest','point_controls','build_receipt','admission','output')),'Explicit phase, inputs, admission and NEW output required')
 args.output=args.output.resolve();need(not args.output.exists() and not args.output.is_relative_to(Path(__file__).resolve().parent),'Output must be NEW and outside publication source');args.output.mkdir(parents=True);result=dict(schema='guarded_s05_replay_v1',passed=False,mode=args.mode,scope=args.scope,resources=[],artifacts=[],score_report=None);write(args.output/'result.json',result);began=time.monotonic()
 try:
  point=import_module(args.point_controls,'_guard_point_contract');binding=bindings(args,point);admission=read(args.admission);result.update(binding=binding,admission_path=str(args.admission.resolve()),admission_sha256=sha(args.admission));(args.output/'admission_snapshot.json').write_bytes(args.admission.read_bytes());write(args.output/'result.json',result)
  need(admission.get('schema')=='s05_execution_admission_v1' and admission.get('status')=='admitted' and admission.get('mode')==args.mode and admission.get('binding')==binding,'Conductor admission mismatch')
  workers=admission['workers'];need(type(workers) is int and (1<=workers<=4 if args.mode=='full' else workers==1),'Worker admission differs');result['workers']=workers
  lease_check(admission);(args.output/'lease_snapshot.json').write_bytes(Path(admission['lease']['snapshot_path']).read_bytes());write(args.output/'active_lease_at_launch.json',read(admission['lease']['active_path']));cap=CAPS['full_'+args.scope if args.mode=='full' else args.mode];need(admission['phase_wall_limit_seconds']==cap,'Phase cap changed');result['phase_wall_limit_seconds']=cap
  end=min(stamp(admission['expires_utc']),stamp(admission['run_deadline_utc'])-dt.timedelta(seconds=1800));remaining=(end-now()).total_seconds();need(remaining>0,'Publication reserve/deadline exhausted');deadline=time.monotonic()+min(cap,remaining);receipts=materialized_receipts(args.manifest)
  def owned_lease():
   need(sha(args.admission)==result['admission_sha256'],'Immutable admission changed');lease_check(admission)
  prior={}
  for kind,item in admission.get('prior',{}).items():prior[kind]=evidence(item['path'],item['sha256'],binding)
  if args.mode!='controls':
   control=prior['controls'];need(control['mode']=='controls','Prior controls mode');archived=read(control['archived_controls']);point_report=read(control['point_controls']) if args.scope=='point' else None;validate_controls(archived,point_report,binding)
  if args.mode=='full':
   for mode in ('pilot','probe_oc','probe_ep'):
    need(prior[mode]['mode']==mode and prior[mode]['workers']==1,'Wrong prerequisite phase/workers');validate_report(read(prior[mode]['score_report']),mode,args.scope,binding,receipts)
   work=admission['workload'];need(sha(work['path'])==work['sha256'],'Workload snapshot drift');estimate=projection(read(work['path']),[prior[k] for k in ('pilot','probe_oc','probe_ep')],args.scope,workers,args.manifest.stat().st_size);result['projection']=estimate
   need(admission.get('resource_admitted') is True and admission['resource_projection']==estimate,'Actual resource admission differs from measured prerequisites')
   need(estimate['projected_seconds']<=min(cap,deadline-time.monotonic()) and estimate['projected_tree_bytes']<=TREE_CAP and estimate['projected_tree_bytes']+HEADROOM<=psutil.virtual_memory().available,'Full resource/deadline admission failed')
  need(psutil.virtual_memory().available>HEADROOM+(INITIAL_RESERVE if args.mode!='full' else 0),'OS/other-work headroom and startup reserve unavailable')
  def launch(command,name):
   remaining=deadline-time.monotonic();need(remaining>0,'Fixed phase deadline exhausted');resource=supervise(command,args.output/name,remaining,TREE_CAP,dict(os.environ),owned_lease);result['resources'].append(resource);write(args.output/'result.json',result);need(resource['passed'],'Supervised child failed/terminated')
  python=[sys.executable,'-B']
  if args.mode=='controls':
   archived_path=args.output/'archived_controls.json';launch(python+[str(args.sources/'replay.py'),'controls','--dll',str(args.dll),'--output',str(archived_path)],'archived_controls_process');result['archived_controls']=str(archived_path)
   point_path=None
   if args.scope=='point':
    point_path=args.output/'point_controls.json';launch(python+[str(args.point_controls),'--sources',str(args.sources),'--dll',str(args.dll),'--build-receipt',str(args.build_receipt),'--output',str(point_path)],'point_controls_process')
   result['point_controls']=str(point_path) if point_path else None;validate_controls(read(archived_path),read(point_path) if point_path else None,binding);paths=[archived_path]+([point_path] if point_path else [])
  elif args.mode in PROBES:
   report=args.output/'probe_report.json';config=args.output/'probe_request.json';write(config,dict(sources=str(args.sources.resolve()),dll=str(args.dll.resolve()),manifest=str(args.manifest.resolve()),identity=PROBES[args.mode],scope=args.scope,report=str(report),admission=str(args.admission.resolve()),admission_sha256=result['admission_sha256'],binding=binding));result['score_report']=str(report);launch(python+[str(Path(__file__).resolve()),'--child-probe',str(config)],'probe_process');validate_report(read(report),args.mode,args.scope,binding,receipts);paths=[report,config]
  else:
   child_output=args.output/'replay';result['score_report']=str(child_output/'report.json');command=python+[str(args.sources/'replay.py'),'run','--scope',args.scope,'--manifest',str(args.manifest),'--dll',str(args.dll),'--controls',prior['controls']['archived_controls'],'--output',str(child_output),'--workers',str(workers)]
   if args.mode=='pilot':command+=['--pilot']
   launch(command,'replay_process');report=child_output/'report.json';result['score_report']=str(report);validate_report(read(report),args.mode,args.scope,binding,receipts)
   journal=[json.loads(s) for s in (child_output/'progress.jsonl').read_text().splitlines() if s.strip()];validate_rows(journal,args.mode,args.scope,receipts);need({identity(x):x for x in journal}=={identity(x):x for x in read(report)['rows']},'Journal/report actual rows differ');paths=[report,child_output/'progress.jsonl',child_output/'binding.json']
  need(bindings(args,point)==binding,'Source/DLL/input drift');owned_lease();result['artifacts']=[dict(path=str(path.resolve()),sha256=sha(path)) for path in paths];result['passed']=True
 except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc))
 finally:
  result['elapsed_seconds']=time.monotonic()-began;result['artifacts']=[dict(path=str(p.resolve()),sha256=sha(p)) for p in sorted(args.output.rglob('*')) if p.is_file() and p!=args.output/'result.json'];write(args.output/'result.json',result)
 print(json.dumps(dict(passed=result['passed'],mode=args.mode,scope=args.scope)));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
