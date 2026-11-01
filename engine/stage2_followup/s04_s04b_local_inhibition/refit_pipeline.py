"""Persistent finer-grid refits overlapped with independent CPU replay."""
import os,sys,json,sqlite3,subprocess,time,signal,hashlib,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=Path('/home/gpt/cuda_integration_20261030T114603Z')
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
 p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def descendants():
 pairs={}
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:pairs[int(p.name)]=int((p/'stat').read_text().rsplit(')',1)[1].split()[1])
   except (OSError,ValueError,IndexError):pass
 found=set();parents={os.getpid()}
 while parents:
  nxt={p for p,parent in pairs.items() if parent in parents and p not in found};found.update(nxt);parents=nxt
 return found
def cleanup():
 children=descendants()
 for sig in (signal.SIGTERM,signal.SIGKILL):
  for pid in children:
   try:os.kill(pid,sig)
   except ProcessLookupError:pass
  time.sleep(.3)
def interrupted(signum,frame):raise SystemExit(128+signum)


def main():
 signal.signal(signal.SIGTERM,interrupted)
 cfg=read(ROOT.parent/'control/refit_config.json');token=os.environ['NUMERICAL_LEASE_TOKEN'];out=ROOT.parent/'results';out.mkdir(exist_ok=True)
 if any(out.iterdir()):raise FileExistsError('nonempty fresh results required')
 for path,h in read(ROOT.parent/'control/input_pins.json').items():
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise RuntimeError('input changed '+path)
 cases={c['case_id']:c for c in cfg['cases']};jobs={};fits={};audits={};anchors=set(cfg['audit_cases']);validated=set();started=time.monotonic();overlap=0.;previous=started;peak=0;last_sample=0;last_print=0
 db=sqlite3.connect(ROOT.parent/'results/refit.sqlite3');db.execute('create table cases(id text primary key,regime integer,status text,fit_report text,audit_passed integer)')
 for cid,c in cases.items():db.execute('insert into cases values(?,?,?,?,?)',(cid,c['regime'],'pending',None,0))
 db.commit();status={'status':'running','total':len(cases),'prior_accepted':0}
 def save():
  nonlocal last_print
  for cid,result in fits.items():
   state=('accepted_refit' if cases[cid]['regime'] in validated else 'provisional') if result.get('status')=='converged' else result.get('status','unresolved')
   db.execute('update cases set status=?,fit_report=?,audit_passed=? where id=?',(state,json.dumps(result),int(cases[cid]['regime'] in validated),cid))
  db.commit();counts=dict(db.execute('select status,count(*) from cases group by status').fetchall())
  status.update(counts=counts,gpu=jobs.get('fit',{}).get('id'),audit=jobs.get('audit',{}).get('id'),validated_regimes=sorted(validated),overlap_seconds=overlap,elapsed_seconds=time.monotonic()-started,observed_gpu_peak_mib=peak)
  write(out/'progress.json',status)
  if time.monotonic()-last_print>30 or not jobs:print(json.dumps(status),flush=True);last_print=time.monotonic()
 def launch(kind,cid):
  c=cases[cid];dest=out/(cid+'_'+kind);args=['taskset','-c','0' if kind=='fit' else '1-3','timeout','--signal=TERM','--kill-after=5s','1750s',sys.executable,'-B',str(ROOT/'refit_worker.py'),'--mode',kind,'--case-dir',c['case_directory'],'--output',str(dest),'--base',str(BASE),'--seed',str(c['seed']),'--regime',str(c['regime']),'--lease-token',token,'--budget-seconds','1740']
  if kind=='audit':args+=['--fit-dir',str(out/(cid+'_fit'))]
  log=(out/(cid+'_'+kind+'.log')).open('x');proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT);jobs[kind]={'id':cid,'dest':dest,'proc':proc,'log':log}
  with (out/'events.jsonl').open('a') as f:f.write(json.dumps({'event':'start','kind':kind,'case':cid,'pid':proc.pid,'elapsed':time.monotonic()-started})+'\n')
 def finish(kind):
  job=jobs[kind];code=job['proc'].poll()
  if code is None:return
  job['log'].close();cid=job['id'];result=read(job['dest']/'report.json') if (job['dest']/'report.json').exists() else {};del jobs[kind]
  with (out/'events.jsonl').open('a') as f:f.write(json.dumps({'event':'finish','kind':kind,'case':cid,'exit_code':code,'elapsed':time.monotonic()-started})+'\n')
  if (result.get('seed'),result.get('regime'),result.get('mode'))!=(cases[cid]['seed'],cases[cid]['regime'],kind):raise RuntimeError('worker identity or incomplete output '+cid)
  if kind=='audit' and result.get('original_digest')!=fits[cid].get('original_digest'):raise RuntimeError('original data changed')
  if kind=='fit':
   if code not in (0,1) or result.get('status') not in ('converged','refinement_required','fit_incomplete','resource_need'):raise RuntimeError('fit infrastructure failure '+cid+': '+str(result.get('error',code)))
   if result.get('status')=='converged' and result.get('passed') is not True:raise RuntimeError('inconsistent convergence receipt')
   fits[cid]=result
  else:
   if code!=0 or result.get('computational_passed') is not True:raise RuntimeError('independent audit discrepancy '+cid+': '+str(result.get('error',code)))
   if result.get('fit_report_sha256')!=hashlib.sha256((out/(cid+'_fit')/'report.json').read_bytes()).hexdigest():raise RuntimeError('audit report binding')
   audits[cid]=result;validated.add(cases[cid]['regime'])
 try:
  while True:
   now=time.monotonic()
   if 'fit' in jobs and 'audit' in jobs:overlap+=now-previous
   previous=now
   if 'fit' in jobs and now-last_sample>=.5:
    used=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip());peak=max(peak,used);last_sample=now
    with (out/'gpu_memory.jsonl').open('a') as f:f.write(json.dumps({'elapsed':now-started,'mib':used,'case':jobs['fit']['id']})+'\n')
    if used>6144:raise RuntimeError('GPU memory admission >6GiB')
   for kind in ['audit','fit']:
    if kind in jobs:finish(kind)
   remaining=(dt.datetime.fromisoformat(cfg['deadline_utc'].replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()
   can_launch=now-started<cfg['admission_seconds'] and remaining>1760
   if 'audit' not in jobs and can_launch:
    pending=[cid for cid in cases if cid in anchors and cid in fits and cid not in audits and fits[cid].get('status')!='resource_need']
    if pending:launch('audit',pending[0])
   if 'fit' not in jobs and can_launch:
    pending=[cid for cid in cases if cid not in fits and (cid in anchors or anchors.issubset(audits))]
    if anchors.issubset(audits) and any(not fits[cid].get('passed') or not audits[cid].get('passed') for cid in anchors):raise RuntimeError('pilot scientific controls failed')
    if pending:launch('fit',pending[0])
   save()
   if not jobs:
    if len(fits)!=len(cases) or not anchors.issubset(audits):status['status']='checkpoint_pending'
    else:status['status']='completed' if all(v['status']=='converged' for v in fits.values()) else 'completed_with_followup'
    save();break
   time.sleep(.25)
 except BaseException as exc:
  status.update(status='stopped',error=str(exc));validated.clear();save();raise
 finally:
  signal.signal(signal.SIGTERM,signal.SIG_IGN);cleanup()
  for job in jobs.values():job['proc'].wait(timeout=3);job['log'].close()
  jobs.clear();save();db.close()
if __name__=='__main__':main()
