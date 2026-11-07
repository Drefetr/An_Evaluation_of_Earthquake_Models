"""Bounded predeclared S02 raw-CSV replay using the existing independent oracle."""
import argparse,importlib.util,json,math,os,sys,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from inspect_saved import read,write,sha,need,check_method

def one(task):
 oracle_path,dll,run,case,out,deadline=task;run=Path(run);out=Path(out)
 sys.path.insert(0,str(Path(oracle_path).resolve().parent));spec=importlib.util.spec_from_file_location('independent_f_oracle',oracle_path);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 recipe=read(run/'S02_STAGED_RECIPE.json')['law'];f=recipe['alternative_generating_fit'];law=dict(T=float(recipe['horizon_days']),coordinate=float(recipe['coordinate_horizon_days']),beta=float(recipe['beta']),gamma=.75*math.log(10),n=.5,ratio=float(f['ratio']),stress=f['stress'],trigger=f['trigger'])
 raw=Path(case['path']);need(sha(raw)==case['history_sha256'],'sample raw history pin');d=np.atleast_1d(np.genfromtxt(raw,delimiter=',',names=True,dtype=float));data=dict(times=d['time_hi'],times_lo=d['time_lo'],event_gaps=d['event_gap'],excess=d['excess'])
 fitfile=run/'s02_fits'/(case['id']+'.json');fitpin=sha(fitfile);saved=read(fitfile);need(saved['id']==case['id'] and saved['history_sha256']==case['history_sha256'],'sample fit/raw identity');need(len(saved['methods'])==2 and {m['procedure'] for m in saved['methods']}=={'M1','M2'},'sample procedure map');native=oracle.Native(dll);results=[];maximum=quad=0.;points=0
 for m in saved['methods']:
  if time.monotonic()>deadline:raise TimeoutError('sample raw audit soft budget')
  name=m['procedure'];tracefile=run/'s02_fits'/(case['id']+'.'+name+'.attempts.jsonl');trace=[json.loads(line) for line in tracefile.read_text().splitlines() if line.strip()];check_method(m,trace,f['pars'],f['trigger']);need(m['status']=='complete','sample producer remains unresolved');ratio=.7 if name=='M1' else 0.
  state=native.state(data,law,'paired',ratio,32,True);high=None
  try:
   high=native.state(data,law,'paired',ratio,64,True);own={}
   for phase in ['null','alternative']:
    if time.monotonic()>deadline:raise TimeoutError('sample raw audit soft budget')
    value=state.evaluate(m[phase]['pars']);refined=high.evaluate(m[phase]['pars']);delta=abs(float(value[0])-m[phase]['nll']);qd=abs(float(value[0]-refined[0]));need(delta<=1e-4 and qd<=1e-4,'independent selected NLL/refined32/64');maximum=max(maximum,delta);quad=max(quad,qd);own[phase]=float(value[0]);points+=2
   glr=2*(own['null']-own['alternative']);delta=abs(glr-m['direct_contrast16']['statistic']);need(delta<=1e-4,'independent sampled GLR');maximum=max(maximum,delta);grad=0.
   for record in m['attempts']:
    if time.monotonic()>deadline:raise TimeoutError('sample raw audit soft budget')
    v=state.evaluate(record['terminal_pars']);delta=abs(float(v[0])-record['terminal_best_nll']);need(delta<=1e-4,'sample all-terminal NLL');maximum=max(maximum,delta);grad=max(grad,oracle.projected(v[1:5],record['terminal_pars'],record['free']));points+=1
   results.append(dict(procedure=name,passed=True,all_terminal_returns=len(m['attempts']),independent_glr=glr,projected_gradient_diagnostic=grad))
  finally:
   state.close()
   if high:high.close()
 need(sha(fitfile)==fitpin and sha(raw)==case['history_sha256'],'sample inputs changed')
 result=dict(case_id=case['id'],forest=case['forest'],h=case['h'],methods=results,fit_sha256=fitpin,raw_sha256=case['history_sha256'],passed=True,evaluated_points=points,maximum_nll_glr_abs_error=maximum,maximum_selected32_64_delta=quad);write(out/(case['id']+'.json'),result);return result

def main():
 p=argparse.ArgumentParser()
 for key in ['run','plan','oracle','dll','dll-sha256','fixture-receipt','saved-inspection','output','lease-token']:p.add_argument('--'+key,required=True)
 p.add_argument('--workers',type=int,choices=[1,2],default=2);p.add_argument('--budget-seconds',type=float,default=850);a=p.parse_args()
 if os.environ.get('NUMERICAL_LEASE_TOKEN')!=a.lease_token:raise RuntimeError('root numerical lease token missing')
 need(0<a.budget_seconds<=850,'sample budget<=850s');run=Path(a.run).resolve();need((run/'S02_FIT_CAMPAIGN_RESULT.json').exists(),'campaign not terminal; do not inspect running outputs');need(sha(a.dll)==a.dll_sha256,'oracle binary SHA');fixture=read(a.fixture_receipt);need(fixture.get('passed') is True and fixture['native_binary_sha256']==a.dll_sha256 and fixture['auditor_source_sha256']==sha(a.oracle),'existing independent oracle fixture/source binding')
 inspected=read(a.saved_inspection);need(inspected.get('passed') is True and inspected.get('complete_methods')==600 and inspected.get('catalogues')==300,'successful full saved inspection required')
 manifest=read(run/'manifest.json');plan=read(a.plan);expected=plan['case_ids'];need(expected==['s001_h0p0','s001_h0p5','s001_h0p9'],'predeclared non-outcome-selected sample');selected=[r for r in manifest['cases'] if r['id'] in expected];need(len(selected)==3 and len({r['id'] for r in selected})==3,'sample identity coverage')
 for path in [run/'manifest.json',run/'S02_STAGED_RECIPE.json',*[run/'s02_fits'/(r['id']+'.json') for r in selected]]:need(sha(path)==inspected['input_pins'][str(path)],'saved inspection input binding')
 out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.monotonic()+a.budget_seconds
 report=dict(status='running',passed=False,scope='three predeclared catalogues/six methods only; selected32/64 and all terminal32 raw reconstruction; no optimization')
 try:
  with ProcessPoolExecutor(max_workers=a.workers) as pool:rows=list(pool.map(one,[(a.oracle,a.dll,str(run),case,str(out),deadline) for case in selected]))
  need(len(rows)==3 and sum(len(r['methods']) for r in rows)==6,'sample method coverage');report.update(status='sampled_raw_passed',passed=True,catalogues=3,methods=6,rows=rows,maximum_nll_glr_abs_error=max(r['maximum_nll_glr_abs_error'] for r in rows),maximum_selected32_64_delta=max(r['maximum_selected32_64_delta'] for r in rows),source_pins={str(Path(x).resolve()):sha(x) for x in [__file__,a.oracle,a.dll,a.plan,a.fixture_receipt,a.saved_inspection,run/'manifest.json',run/'S02_STAGED_RECIPE.json']})
 except BaseException as exc:report.update(status='sampled_raw_failed',error_type=type(exc).__name__,error=str(exc));raise
 finally:write(out/'report.json',report)

if __name__=='__main__':main()
