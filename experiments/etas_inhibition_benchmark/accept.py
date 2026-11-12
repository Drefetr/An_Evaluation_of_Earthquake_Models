"""Refine pilot states with frozen source and enforce independent integration gates.

Pilot values are initial parameters/background weights only. Every accepted
likelihood, gradient, optimizer return and held-out score is recomputed here.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time,platform
import numpy as np
from scipy.optimize._numdiff import approx_derivative
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from experiments.etas_inhibition_benchmark.native import build,Native
from experiments.etas_inhibition_benchmark.acceptance_protocol import construct_starts,traced_fit,Budget,budget_objective

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def accepted_case(module,case,pilot_path,out,native,budget):
    initial=json.loads(pilot_path.read_bytes());train,tm,test,vm,sources=module.inputs(case);region=module.Region(train['rectangles'])
    bg=module.Background(train['event_xy'],region,tm['kde_bandwidth'],np.asarray(initial['background_weights']))
    model=module.Model(train,tm,bg);model.native=native;model.objective=budget_objective(model.objective,budget.check)
    warm=[np.asarray(r['parameters']) for r in initial['null']['records']]
    null=module.fit(model,warm,False)
    if not null['complete']:raise RuntimeError('incomplete final null starts')
    x0=np.asarray(null['selected']['parameters']);inh_warm=[np.asarray(r['parameters']) for r in initial['inhibited']['records']]
    # Independent finite-difference check at the actual training optimum.
    numeric=approx_derivative(lambda x:model.objective(np.r_[x,x0[8:]],False)[0],x0[:8],method='3-point',rel_step=1e-5).ravel()
    analytic=model.objective(x0,False)[1][:8];gradient_error=float(np.max(abs(numeric-analytic)))
    if gradient_error>1e-4:raise ArithmeticError(('observed gradient control',gradient_error))
    rounds=[]
    for power in range(14,20):
        budget.check();proposal=model.node_setup(x0,power,20261201+power)
        specifications=construct_starts(x0,inh_warm)
        inh=traced_fit(module,model,specifications,power,out/'training_traces'/f'power_{power}',budget.check)
        if not inh['complete']:raise RuntimeError('incomplete final inhibited starts')
        if not inh['interior_start_coverage']['passed']:raise RuntimeError('prescribed positive starts did not actually execute at final power')
        selected=np.asarray(inh['selected']['parameters'])
        if selected[8]==0:
            # A floor return is the same fitted procedure. Polish its nuisance
            # vector in the null arm as well, then use one exact common floor.
            polished=module.fit(model,[selected],False)
            if not polished['complete']:raise RuntimeError('failed shared-null polish')
            if polished['selected']['nll']<null['selected']['nll']:
                null['selected']=polished['selected'];null['floor_polish']=polished
            x0=np.asarray(null['selected']['parameters']);inh['selected']=dict(null['selected'],nested_null=True);selected=x0.copy()
        if null['selected']['nll']<=inh['selected']['nll']:
            inh['selected']=dict(null['selected'],nested_null=True);selected=x0.copy()
        check_power=min(power+3,21);checks=[]
        for seed in range(20261230,20261234):
            budget.check()
            if selected[8]>0:model.node_setup(x0,check_power,seed)
            checks.append(model.objective(selected,True,True)['nll'])
        mean=float(np.mean(checks));se=float(np.std(checks,ddof=1)/2);bias=abs(mean-inh['selected']['nll']);benefit=null['selected']['nll']-mean
        passed=se<=.02 and bias<=max(.05,5*se) and benefit>=-max(.02,3*se)
        round_=dict(training_power=power,check_power=check_power,proposal=proposal,construction_null_parameters=specifications[0]['initial_parameters'],start_protocol=specifications,interior_start_coverage=inh['interior_start_coverage'],null=null,inhibited=inh,independent_training_nll=checks,independent_training_mean=mean,integration_standard_error=se,fit_objective_difference=bias,training_gain_mean=benefit,passed=passed)
        rounds.append(round_);module.write(out/'progress.json',dict(case=case,rounds=rounds));print('acceptance',case,power,passed,se,bias,benefit,flush=True)
        if passed:break
        inh_warm=[selected,*[np.asarray(r['parameters']) for r in inh['records']]]
    else:raise ArithmeticError('independent training integration did not stabilize')
    evaluation=module.Model(test,vm,bg);evaluation.native=native;evaluation.objective=budget_objective(evaluation.objective,budget.check);scores=[]
    for check_power in range(check_power,22):
        scores=[]
        for seed in range(20261250,20261254):
            budget.check()
            proposal=evaluation.node_setup(x0,check_power,seed) if selected[8]>0 else dict(nested_null_exact=True)
            s0=evaluation.objective(x0,False,True);s1=evaluation.objective(selected,True,True)
            scores.append(dict(seed=seed,proposal=proposal,null=s0,inhibited=s1,gain=s0['nll']-s1['nll']))
        gains=np.array([r['gain'] for r in scores]);mean=float(gains.mean());se=float(gains.std(ddof=1)/2)
        if se<=min(.02,.01*max(1,abs(mean))):break
    else:raise ArithmeticError('held-out integration did not stabilize')
    result=dict(schema='accepted_magnitude_scaled_etas_inhibition_interior_v2',case=case,passed=True,parameter_names=module.NAMES,bounds=module.BOUNDS,
        n_train=len(train['event_time']),n_test=len(test['event_time']),training_rounds=rounds,null=null,inhibited=inh,
        background_weights=bg.weights.tolist(),background_bandwidth_km=bg.h,background_floor=.05,declustering_initialization_sha256=sha(pilot_path),
        background_estimation='Five training-only immigrant-probability KDE weighting iterations; weights frozen for the matched final joint fits. Leave-self-out training event KDE; held-out background uses full frozen training density.',
        spatial='Unweighted full-plane normalized inverse-power ETAS with sigma0 exp(alpha_s (M-M0)); exact regional leakage.',
        inhibition='Total intensity exp(-eta G), mark exp(gamma (M-M0)), ell0 10^(0.5 (M-M0)), exponential time relaxation.',
        actual_training_gradient_max_error=gradient_error,test_scores=scores,test_gain_mean=mean,test_integration_standard_error=se,
        test_integration_power=check_power,source_cache_sha256={k:v['cache']['sha256'] for k,v in sources.items()})
    module.write(out/'result.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',default='all');p.add_argument('--native-threads',type=int,default=2);p.add_argument('--backend',choices=('cpu','cuda'),default='cpu');p.add_argument('--model-source',default='run_frozen_20261111.py');p.add_argument('--wall-seconds',type=float,default=1200);a=p.parse_args()
    if a.wall_seconds<=0:raise ValueError('Positive wall budget required')
    a.output.mkdir(parents=True,exist_ok=False);folder=Path(__file__).parent;budget=Budget(a.wall_seconds)
    if Path(a.model_source).name!=a.model_source:raise ValueError('model source must be a filename in the benchmark module')
    frozen=folder/a.model_source;source_files=[Path(__file__),frozen,folder/'native.py',folder/'pairs.cpp',folder/'acceptance_protocol.py']
    if a.backend=='cuda':source_files += [folder/'gpu_native.py',folder/'gpu_pairs.cu']
    pins={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in source_files}
    spec=importlib.util.spec_from_file_location('_frozen_etas_acceptance',frozen);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if a.backend=='cuda':
        from experiments.etas_inhibition_benchmark.gpu_native import build as build_gpu,Native as GpuNative
        dll=build_gpu(ROOT/'build/etas_benchmark_gpu_20261111');native=GpuNative(dll)
    else:dll=build(ROOT/'build/etas_benchmark_native_20261111'/platform.system());native=Native(dll,threads=a.native_threads)
    module.write(a.output/'launch.json',dict(source_sha256=pins,native_binary_sha256=sha(dll),threads=a.native_threads,backend=a.backend,cooperative_wall_seconds=a.wall_seconds))
    cases=[f'california_fold_{i}' for i in range(3)] if a.case=='all' else [a.case];rows=[]
    with threadpool_limits(limits=1):
        for case in cases:
            path=a.pilot/case/'result.json'
            if not path.exists():raise FileNotFoundError('pilot initializer not yet complete: '+str(path))
            r=accepted_case(module,case,path,a.output/case,native,budget);rows.append(r)
    for path,expected in pins.items():
        if sha(ROOT/path)!=expected:raise RuntimeError('source drift during final acceptance: '+path)
    module.write(a.output/'summary.json',dict(schema='accepted_etas_inhibition_benchmark_interior_v2',passed=True,source_sha256=pins,native_binary_sha256=sha(dll),cooperative_wall_seconds=a.wall_seconds,prescribed_positive_starts=[[.05,10,2],[.2,20,5],[.5,50,30]],all_final_power_interior_start_coverage_passed=all(r['training_rounds'][-1]['interior_start_coverage']['passed'] for r in rows),rows=[{k:r[k] for k in ('case','n_train','n_test','test_gain_mean','test_integration_standard_error')} for r in rows]))
if __name__=='__main__':main()
