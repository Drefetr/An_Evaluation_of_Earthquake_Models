import pathlib,json,subprocess,datetime,os
cmd=['/home/gpt/hostile_remediation_20261111/venv/bin/python', '-B', 'experiments/etas_inhibition_benchmark/accept.py', '--backend', 'cuda', '--model-source', 'run_frozen_gpu_20261111.py', '--pilot', 'validation/live_results/etas_gpu_pilot_states_20261111', '--output', 'validation/live_results/etas_inhibition_benchmark_interior_20261112', '--wall-seconds', '1200']
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
p=subprocess.Popen(cmd,cwd='/home/gpt/hostile_remediation_20261111/repo',env=env)
pathlib.Path('/home/gpt/hostile_remediation_20261111/repo/validation/remote_runs/etas_interior_20261112/child_pid.json').write_text(json.dumps(dict(pid=p.pid)))
code=p.wait()
pathlib.Path('/home/gpt/hostile_remediation_20261111/repo/validation/remote_runs/etas_interior_20261112/exit.json').write_text(json.dumps(dict(exit_code=code,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())))
