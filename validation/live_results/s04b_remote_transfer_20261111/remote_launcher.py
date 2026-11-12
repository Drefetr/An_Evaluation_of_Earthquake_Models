import datetime,hashlib,json,os,platform,subprocess
from pathlib import Path
base=Path('/home/gpt/hostile_remediation_20261111');repo=base/'repo';out=base/'results/s04b';receipt=out/'launch.json'
assert not receipt.exists(), 'Recovery lane already launched'
env=dict(os.environ,S04B_COMPLETION_ROOT=str(out),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',BLIS_NUM_THREADS='2')
manifest=json.loads((repo/'REMOTE_TRANSFER_MANIFEST.json').read_text())
for entry in manifest['files']:
 if entry['path'].startswith(('experiments/s04b_completion/','experiments/s04b_joint_nuisance/','experiments/s04b_exposure_refinement/','experiments/s04b_joint_execution/')):
  assert hashlib.sha256((repo/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
records=[]
for case in ('S5_broad_long_imm_seed410518','S6_narrow_short_total_seed410615'):
 command=[str(base/'venv/bin/python'),'-B','scripts/fit_joint_refined_cpu.py','recover','--case-id',case,'--wall-seconds','7200','--saved-evidence','validation/live_results/s04b_remote_transfer_20261111/saved_evidence','--resume-from','validation/live_results/s04b_joint_complete_20261111/recovery/'+case]
 with (out/(case+'.log')).open('w') as log:
  process=subprocess.Popen(command,cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 records.append(dict(case_id=case,pid=process.pid,command=command,threads=2,log=str(out/(case+'.log'))))
value=dict(host=platform.node(),platform=platform.platform(),launched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),jobs=records,transfer_manifest_sha256=hashlib.sha256((repo/'REMOTE_TRANSFER_MANIFEST.json').read_bytes()).hexdigest())
receipt.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
