from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
import psutil
run=Path(__file__).resolve().parent;repo=run/'checkout';out=run/'numerical'
out.mkdir(exist_ok=False)
env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
start=time.monotonic()
record={'schema':'bounded_scalar_execution_v1','started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':False,'limits':{'total_wall_seconds':7200,'pilot_wall_seconds':600,'sampled_process_tree_rss_bytes':2**31,'poll_seconds':.1},'memory_scope':'RSS sampled across owned process tree every0.1s; threshold triggers termination. Sampling does not certify an instantaneous hard OS limit.','phases':[]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(): (out/'execution.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
def stop_tree(proc):
    try: children=psutil.Process(proc.pid).children(recursive=True)
    except psutil.NoSuchProcess:children=[]
    for child in reversed(children):
        try:child.kill()
        except psutil.NoSuchProcess:pass
    if proc.poll() is None:proc.kill()
    proc.wait(timeout=30)
def phase(name,command,cap):
    if psutil.virtual_memory().available<2**31:raise RuntimeError('Insufficient memory headroom')
    log=out/(name+'.log');t=time.monotonic();seen={};peak=0;reason=None
    with log.open('wb') as f:
        proc=subprocess.Popen(command,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
        while proc.poll() is None:
            try:tree=[psutil.Process(proc.pid)]+psutil.Process(proc.pid).children(recursive=True)
            except psutil.NoSuchProcess:tree=[]
            rss=0
            for p in tree:
                try:seen[p.pid]=p.create_time();rss+=p.memory_info().rss
                except psutil.NoSuchProcess:pass
            peak=max(peak,rss)
            if time.monotonic()-t>cap or time.monotonic()-start>7200:reason='wall_limit'
            if rss>2**31:reason='sampled_tree_memory_limit'
            if reason:stop_tree(proc);break
            time.sleep(.1)
        code=proc.wait()
    remaining=[]
    for pid,created in seen.items():
        try:
            p=psutil.Process(pid)
            if p.is_running() and abs(p.create_time()-created)<.01:remaining.append(pid)
        except psutil.NoSuchProcess:pass
    row={'name':name,'command':command,'pid':proc.pid,'returncode':code,'wall_seconds':time.monotonic()-t,'sampled_peak_tree_rss':peak,'owned_process_identities':seen,'live_owned_processes_at_return':remaining,'stop_reason':reason,'log_sha256':sha(log)}
    record['phases'].append(row);write();print(json.dumps(row),flush=True)
    if code or reason or remaining:raise RuntimeError('Phase failed: '+name)
try:
    review=json.loads((run/'review_floor_code/result.json').read_text())
    record['source_review_sha256']=sha(run/'review_floor_code/result.json')
    record['protocol_sha256']=sha(repo/'experiments/s04b_refitted_floor/protocol.json')
    assert record['protocol_sha256']=='a1794b96655812cc83291f56f6f3fe58a51baca98d96aa2de089ebcc8c9d7a29'
    # The conductor checks the review's actual verdict before launching this supervisor.
    phase('fixtures',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_s04b_refitted_floor.py','-v'],300)
    phase('native_build',[sys.executable,'-B',str(run/'build_floor_native.py')],600)
    native=repo/'build/refitted_floor_native'
    common=[sys.executable,'-B','experiments/s04b_refitted_floor/run.py','--radial',str(native/'radial.dll'),'--build-receipt',str(native/'build_receipt.json'),'--acknowledge-reviewed-numerical-admission','TRAIN_ONLY_FIXED_ROSTER']
    pilot=out/'pilot';full=out/'full'
    phase('pilot',common+['--phase','pilot','--output',str(pilot)],600)
    assert json.loads((pilot/'result.json').read_text())['passed']
    phase('full',common+['--phase','full','--pilot',str(pilot),'--output',str(full)],7200-(time.monotonic()-start))
    result=json.loads((full/'result.json').read_text())
    assert result['passed'] and result['completed_cases']==80 and result['historical_floor_checks']==480
    record.update(passed=True,full_result_sha256=sha(full/'result.json'),pilot_result_sha256=sha(pilot/'result.json'),completed_unique_scalar_fits=80)
except Exception as e:
    record.update(error_type=type(e).__name__,error=str(e))
    raise
finally:
    record['wall_seconds']=time.monotonic()-start;record['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write()

