"""Install the exact shipped catalogue, refit the frozen procedure once, compare.

This invokes the unchanged numerical entry point. Use --compare-existing to
inspect an already completed result without running another fit.
"""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('observed_result_comparator',ROOT/'reproduction/observed/compare.py')
comparator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparator)


def execute(argv,output,name,environment):
    with (output/(name+'.stdout.txt')).open('xb') as stdout,(output/(name+'.stderr.txt')).open('xb') as stderr:
        completed=subprocess.run(argv,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr,check=False)
    return completed.returncode


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New directory; existing outputs are refused.')
    parser.add_argument('--compare-existing',type=Path,help='Compare this completed result without refitting or installing input.')
    args=parser.parse_args(argv)
    if args.output.exists():print('Refusing to overwrite output directory',file=sys.stderr);return 2
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    began=time.monotonic()
    result={'schema_version':1,'passed':False,'started_utc':datetime.now(timezone.utc).isoformat(),
            'mode':'compare_existing' if args.compare_existing else 'fresh_frozen_refit','fit_executed':False}
    try:
        manifest=comparator.load_manifest()
        result['repository_identity']=comparator.verify_repository(manifest)
        environment=os.environ.copy()
        environment.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        if args.compare_existing:
            actual=args.compare_existing.resolve()
        else:
            protocol=json.loads((ROOT/manifest['current_protocol']['path']).read_text())
            installed=ROOT/'engine'/protocol['data']['path']
            if installed.exists():
                comparator.read_pinned(installed,protocol['data']['sha256'])
            else:
                code=execute([sys.executable,'-B',str(ROOT/'scripts/install_catalogue.py'),str(ROOT/manifest['bundled_csv'])],output,'install',environment)
                if code:raise ValueError('catalogue_install_failed')
            comparator.read_pinned(installed,protocol['data']['sha256'])
            actual=output/'observed.json'
            result['fit_executed']=True
            code=execute([sys.executable,'-B',str(ROOT/'scripts/run_observed.py'),'--output',str(actual)],output,'fit',environment)
            result['fit_exit_code']=code
            if code:raise ValueError('frozen_fit_failed_or_incomplete')
        comparison=comparator.run_comparison(actual)
        with (output/'comparison.json').open('x',encoding='utf-8') as stream:
            json.dump(comparison,stream,indent=2,allow_nan=False);stream.write('\n')
        result.update(passed=comparison['passed'],actual_result_sha256=comparison['actual_result_sha256'],
                      comparison='comparison.json',counts=comparison['counts'])
    except Exception as error:
        result.update(error_type=type(error).__name__,error=str(error))
    result.update(completed_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-began)
    with (output/'result.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'passed':result['passed'],'mode':result['mode'],'result':'result.json'}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
