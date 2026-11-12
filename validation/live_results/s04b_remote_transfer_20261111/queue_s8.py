import datetime,json,os,subprocess,time
from pathlib import Path
base=Path('/home/gpt/hostile_remediation_20261111');out=base/'results/s8';out.mkdir(parents=True,exist_ok=True)
receipt=out/'launch.json';assert not receipt.exists()
while True:
 result=base/'results/s04b/recovery/S6_narrow_short_total_seed410615/result.json'
 if result.exists():
  status=json.loads(result.read_text())
  if not status.get('passed'):
   (out/'queue_failed.json').write_text(json.dumps(dict(reason='S6 did not pass; S8 not launched',s6_result=status)))
   raise SystemExit(1)
  break
 time.sleep(10)
env=dict(os.environ,S04B_COMPLETION_ROOT=str(base/'results/s04b'),S8_RESULTS_ROOT=str(out),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',BLIS_NUM_THREADS='2')
command=[str(base/'venv/bin/python'),'-B','-m','experiments.s04b_completion.s8_batch','--workers','1','--resume-from','validation/live_results/s8_moderate_20261111']
with (out/'batch.log').open('w') as log:process=subprocess.Popen(command,cwd=base/'repo',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt.write_text(json.dumps(dict(pid=process.pid,command=command,threads_per_worker=2,workers=1,launched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),gate='S6 complete scientific result passed'),indent=2)+'\n')
