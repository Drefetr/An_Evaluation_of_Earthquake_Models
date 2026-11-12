"""Run the exclusive GPU benchmark lane and retain stage PIDs/exit receipts."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--python',type=Path,required=True);p.add_argument('--run-directory',type=Path,required=True);a=p.parse_args();root=a.repo.resolve();run=a.run_directory.resolve();run.mkdir(parents=True,exist_ok=False)
    folder=root/'experiments/etas_inhibition_benchmark';files=[folder/n for n in ('run_frozen_gpu_20261111.py','accept.py','gpu_native.py','gpu_pairs.cu','native.py','pairs.cpp','remote_campaign.py')];pins={p.relative_to(root).as_posix():sha(p) for p in files}
    common=root/'validation/live_results/etas_gpu_pilot_states_20261111';first=root/'validation/live_results/etas_inhibition_benchmark_20261111/california_fold_0/result.json';dest=common/'california_fold_0/result.json';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(first,dest)
    commands=[]
    for i in (1,2):
        out=root/f'validation/live_results/etas_gpu_pilot_run_F{i}_20261111'
        commands.append((f'pilot_F{i}',[str(a.python),'-B','experiments/etas_inhibition_benchmark/run_frozen_gpu_20261111.py','--backend','cuda','--case',f'california_fold_{i}','--power','13','--check-power','16','--output',str(out)],out/f'california_fold_{i}/result.json',common/f'california_fold_{i}/result.json'))
    accepted=root/'validation/live_results/etas_inhibition_benchmark_accepted_20261111'
    commands.append(('acceptance',[str(a.python),'-B','experiments/etas_inhibition_benchmark/accept.py','--backend','cuda','--model-source','run_frozen_gpu_20261111.py','--pilot',str(common),'--output',str(accepted)],None,None))
    environment=os.environ.copy();environment.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1');progress=[]
    (run/'source_binding.json').write_text(json.dumps(dict(source_prelaunch_sha256=pins,first_pilot_initializer_sha256=sha(first),started_utc=stamp()),indent=2)+'\n')
    for name,cmd,source,destination in commands:
        for rel,expected in pins.items():
            if sha(root/rel)!=expected:raise RuntimeError('source drift before '+name+': '+rel)
        tick=dict(stage=name,command=cmd,started_utc=stamp());print('starting',name,flush=True)
        with (run/(name+'.stdout.log')).open('wb') as out,(run/(name+'.stderr.log')).open('wb') as err:
            process=subprocess.Popen(cmd,cwd=root,env=environment,stdout=out,stderr=err)
            tick['pid']=process.pid;(run/(name+'.launch.json')).write_text(json.dumps(tick,indent=2)+'\n');tick['exit_code']=process.wait()
        tick['completed_utc']=stamp();progress.append(tick);(run/'progress.json').write_text(json.dumps(progress,indent=2)+'\n');print('finished',name,tick['exit_code'],flush=True)
        if tick['exit_code']:
            (run/'exit.json').write_text(json.dumps(dict(passed=False,failed_stage=name,exit_code=tick['exit_code'],completed_utc=stamp()),indent=2)+'\n');return tick['exit_code']
        if source is not None:
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    for rel,expected in pins.items():
        if sha(root/rel)!=expected:raise RuntimeError('final source drift '+rel)
    (run/'exit.json').write_text(json.dumps(dict(passed=True,exit_code=0,completed_utc=stamp(),accepted_summary_sha256=sha(accepted/'summary.json')),indent=2)+'\n');return 0

if __name__=='__main__':raise SystemExit(main())
