"""Two-worker S8 campaign; failures retained, no replacement histories."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def one(seed,resume_from=None):
    folder=Path(os.environ.get('S8_RESULTS_ROOT',ROOT/'validation/live_results/s8_moderate_20261111'));folder.mkdir(parents=True,exist_ok=True)
    with (folder/(str(seed)+'.log')).open('w') as log:
        command=[sys.executable,'-B','-m','reproduction.synthetic.s8_moderate','fit','--seed',str(seed)]
        if resume_from:command+=['--resume-from',str(resume_from)]
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps(dict(seed=seed,returncode=result.returncode)),flush=True)
    return result.returncode
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=1);p.add_argument('--resume-from',type=Path);args=p.parse_args()
    seeds=json.loads((ROOT/'reproduction/synthetic/s8_moderate_total/protocol.json').read_text())['seeds']
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        codes=[job.result() for job in as_completed([pool.submit(one,seed,args.resume_from) for seed in seeds])]
    raise SystemExit(int(any(codes)))
