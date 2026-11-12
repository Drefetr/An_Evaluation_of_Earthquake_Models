import subprocess,json,datetime,pathlib
cmd=['/home/gpt/hostile_remediation_20261111/venv/bin/python', '-B', 'experiments/etas_inhibition_benchmark/gpu_controls.py', '--output', 'validation/live_results/etas_gpu_controls_20261111.json']
p=subprocess.run(cmd,cwd='/home/gpt/hostile_remediation_20261111/repo')
pathlib.Path('/home/gpt/hostile_remediation_20261111/repo/validation/remote_runs/etas_gpu_controls_20261111/exit.json').write_text(json.dumps(dict(exit_code=p.returncode,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())))
