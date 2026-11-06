from pathlib import Path
import datetime,json,psutil
run=Path(__file__).resolve().parent
p=psutil.Process(35492)
assert p.name().lower()=='vctip.exe'
assert abs(p.create_time()-1793964804.270686)<.001
assert not p.children(recursive=True)
identity={'pid':p.pid,'name':p.name(),'created':p.create_time(),'cmdline':p.cmdline()}
p.terminate();p.wait(timeout=15)
old=json.loads((run/'numerical/execution.json').read_text())
remaining=[]
for phase in old['phases']:
 for pid,created in phase['owned_process_identities'].items():
  try:
   p=psutil.Process(int(pid))
   if p.is_running() and abs(p.create_time()-created)<.01:remaining.append(p.pid)
  except psutil.NoSuchProcess:pass
assert not remaining,remaining
result={'passed':True,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'diagnosis':'MSVC compiler spawned its own vctip telemetry helper, which remained after successful compilation. Supervisor refused progression before numerical histories were scored.','terminated_exact_owned_helper':identity,'remaining_owned_processes':remaining,'scientific_histories_executed':0,'successful_controls_retained':19,'native_compile_exit_code':0}
(run/'compiler_helper_recovery.json').write_text(json.dumps(result,indent=2)+'\n')
s=(run/'execute_floor.py').read_text()
s=s.replace("out=run/'numerical'","out=run/'numerical_continuation'")
oldphases="    phase('fixtures',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_s04b_refitted_floor.py','-v'],300)\n    phase('native_build',[sys.executable,'-B',str(run/'build_floor_native.py')],600)"
newphases="""    prior=json.loads((run/'numerical/execution.json').read_text())
    recovery=json.loads((run/'compiler_helper_recovery.json').read_text())
    assert recovery['passed'] and recovery['scientific_histories_executed']==0
    assert all(p['returncode']==0 for p in prior['phases'])
    record['retained_controls_and_build']={'execution_sha256':sha(run/'numerical/execution.json'),'recovery_sha256':sha(run/'compiler_helper_recovery.json'),'fixtures':19,'native_compile_exit_code':0,'scope':'Prior attempt stopped only for owned compiler-helper quiescence; no history scored.'}"""
assert oldphases in s;s=s.replace(oldphases,newphases)
(run/'execute_floor_continuation.py').write_text(s,encoding='utf-8')
print(json.dumps(result))

