"""Rebuild S04B likelihoods from exact histories and saved training fits.

Default: all 80 cases, CPU only, selected/floor states, train16 and test32.
Outputs are new artifacts; archived inputs are never rewritten.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time
from types import SimpleNamespace

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key] = '1'
import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from native import KEYS, Native, build, sha

MODES = [('LI',0,0),('LIplus_immigrant',1,0),('LIplus_inclusive',1,1)]
TOL = 1e-4
_SCORE_WORKER = None


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def resolve_input(root, relative):
    if Path(relative).is_absolute():
        raise ValueError('Absolute input paths are not allowed')
    path = (Path(root)/relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Input path escapes bundle')
    return path


def verify_inputs(root, manifest):
    seen = set()
    for record in manifest['files']:
        name = record['path']
        if name in seen:
            raise ValueError('Duplicate manifest path: '+name)
        seen.add(name)
        path = resolve_input(root, name)
        if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
            raise ValueError('Input changed: '+name)
    cases = manifest['s04b']['cases']
    if len(cases)!=80 or len({r['case_id'] for r in cases})!=80:
        raise ValueError('S04B roster must have 80 unique cases')
    for regime in range(4,8):
        if sorted(r['seed'] for r in cases if r['regime']==regime)!=list(range(410001+100*regime,410021+100*regime)):
            raise ValueError('Incomplete frozen seed roster')
    bank = read(resolve_input(root,manifest['s01']['bank']))
    if len(bank['cases'])!=2149 or len({r['id'] for r in bank['cases']})!=2149:
        raise ValueError('S01 roster must have 2149 unique histories')
    roles = {r:sum(c['role']==r for c in bank['cases']) for r in bank['roles']}
    if roles!={'reference':999,'null_query':1000,'alternative_query':150}:
        raise ValueError('S01 role denominator mismatch')
    return dict(files=len(seen),s04b_histories=80,s01_histories=2149,s01_roles=roles)


def scientific_modules():
    """Load exact archived modules without relying on machine-specific paths."""
    modules = {}
    saved = {}
    try:
        for name in ('spatial','geometry_plan','generator','controls_campaign'):
            alias = '_synthetic_archived_'+name
            spec = importlib.util.spec_from_file_location(alias,HERE/'source'/(name+'.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[alias] = module
            saved[name] = sys.modules.get(name)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            modules[name] = module
    finally:
        for name, old in saved.items():
            if old is None:
                sys.modules.pop(name,None)
            else:
                sys.modules[name] = old
    return modules['controls_campaign']


def grid_digest(data):
    digest = hashlib.sha256()
    for key in KEYS:
        value = np.ascontiguousarray(data[key])
        digest.update(key.encode());digest.update(str(value.dtype).encode())
        digest.update(str(value.shape).encode());digest.update(value.tobytes())
    return digest.hexdigest()


def construct(c, rows, case, geometry, phase, order):
    """Frozen refit_worker/refine_worker constructor; all parents retained."""
    name = c.G.MATCHED_NAMES[case['regime']-4]
    _, background, eta, ell, psi = c.G.ROSTER[name]
    law = c.G.Law(name,case['seed'],background,eta,ell,psi)
    gm = c.G.fitting_metadata(law)
    pars = [law.a,law.d,law.n,np.log(law.c),law.p]
    start,end = (30,395) if phase=='train' else (395,760)
    m = dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
    a = c.canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),np.asarray(gm['kde_weight']),m,pars,geometry)
    plan_a = dict(rectangles=a['rectangles'],reference_pi=a['reference_pi'],kde_xy=a['kde_training_xy'],kde_weight=a['kde_weight'],kde_normalizer=a['kde_normalizers'],parent_xy=a['parent_xy'])
    plans, info = c._adaptive_area_space(plan_a,dict(bg_floor=m['bg_floor'],kde_h=m['kde_h']),[order],1e-8,20)
    plan = plans[order]; xy = plan['space_xy'];b,cells = c.background(xy,a,m)
    space = np.ascontiguousarray(np.column_stack([xy,plan['space_weight']/b,b,a['reference_pi'][cells]/a['cell_areas'][cells]]))
    times,weights = c.time_plan(a['parent_time'],m['start'],m['end'],np.exp(pars[3]),2*order)
    f = c.S.features(a,m,pars[3:5]);baseline = c.S.evaluate(f,pars[:3])[0]
    parents = np.ascontiguousarray(np.column_stack([a['parent_time'],a['parent_xy'],a['parent_excess'],a['parent_fertility'],a['parent_normalizer']]))
    events = np.ascontiguousarray(np.column_stack([a['event_time'],a['event_xy'],a['event_background_density'],pars[2]*f['hp'],a['reference_pi'][a['event_cell'].astype(int)]/a['cell_areas'][a['event_cell'].astype(int)]]))
    meta = np.array([*pars[:3],np.exp(pars[3]),pars[4],m['T0'],baseline['compensator'],f['marks'],m['sigma']])
    return dict(parents=parents,events=events,space=space,times=times,weights=weights,meta=meta), info


def chunks(data,budget):
    """Partition spatial integration only; count event/base terms once."""
    np_,ne,ns,nt = (len(data[k]) for k in KEYS[:4])
    shared = 8*(9*np_+10*ne+5*nt+nt*np_)+4*(nt+1)
    perrow = 8*(9+2*np_+2*nt)
    count = int((budget-shared)//max(1,perrow))
    if count<1:
        raise MemoryError('Shared native arrays exceed chunk budget')
    for start in range(0,ns,count):
        item = dict(data)
        item['space'] = np.ascontiguousarray(data['space'][start:start+count])
        item['meta'] = data['meta'].copy()
        if start:
            item['events'] = np.empty((0,6),dtype=np.float64)
            item['meta'][6:8] = 0.
        yield item


def saved_selection(fit):
    eligible = [r for r in fit['records'] if r.get('success') and r.get('finite_feasible')]
    eligible.append(dict(start=-1,pars=fit['floor'],nll=fit['floor_nll']))
    winner = min(eligible,key=lambda r:(r['nll'],r['start']>=0,r['start']))
    if winner['pars']!=fit['selected']['pars'] or winner['nll']!=fit['selected']['nll']:
        raise ValueError('Saved fit is not the training-selected state')
    if fit['status']!='complete' or {r['start'] for r in eligible if r['start']>=0}!=set(range(8)):
        raise ValueError('Required training starts are incomplete')
    return fit['selected']['pars'],fit['floor']


def evaluate_phase(native,data,fits,threads,budget,deadline):
    jobs = [(name,plus,inclusive,label,p) for name,plus,inclusive in MODES for label,p in zip(('selected','floor'),saved_selection(fits[name]))]
    totals = {(name,label):np.zeros(6) for name,_,_,label,_ in jobs}
    count = 0
    for piece in chunks(data,budget):
        if time.monotonic()>deadline:
            raise TimeoutError('Campaign deadline reached; incomplete outputs retained')
        handle = native.create(piece)
        try:
            def call(job):
                name,plus,inclusive,label,p = job
                return name,label,native.evaluate(handle,p,plus,inclusive)
            with ThreadPoolExecutor(max_workers=threads) as pool:
                for name,label,value in pool.map(call,jobs):
                    totals[name,label] += value
        finally:
            native.free(handle)
        count += 1
    return {name:{label:totals[name,label].tolist() for label in ('selected','floor')} for name,_,_ in MODES},count


def assert_close(actual,expected,label,tolerance=TOL):
    if not math.isfinite(actual) or abs(actual-expected)>tolerance:
        raise ArithmeticError(f'{label}: {actual!r} versus {expected!r}, absolute tolerance {tolerance}')


def score_case(root,case,c,native,geometry,args,deadline,report_path=None):
    started = time.monotonic()
    with np.load(resolve_input(root,case['history']),allow_pickle=False) as loaded:
        rows = np.ascontiguousarray(loaded['rows'])
    if hashlib.sha256(rows.tobytes()).hexdigest()!=case['rows_sha256']:
        raise ValueError('Decompressed history array pin mismatch')
    fits = {n:read(resolve_input(root,p)) for n,p in case['fits'].items()}
    states = read(resolve_input(root,case['states']))
    expected = read(resolve_input(root,case['expected']))
    report = dict(case_id=case['case_id'],seed=case['seed'],regime=case['regime'],passed=False,phases={})
    if report_path:write(report_path,report)
    computed = {}
    for phase,order in [('train',16),('test',32)]:
        if time.monotonic()>deadline:
            raise TimeoutError('Campaign deadline reached')
        data,geometry_info = construct(c,rows,case,geometry,phase,order)
        key = f'order{order}_{phase}'
        count = len(data['events'])
        if count!=case['n_'+phase]:
            raise ValueError('Rebuilt target denominator differs')
        values,nchunks = evaluate_phase(native,data,fits,args.threads,args.chunk_mib*2**20,deadline)
        digest = grid_digest(data)
        checks = []
        for name,_,_ in MODES:
            for label,p in zip(('selected','floor'),saved_selection(fits[name])):
                index = next(i for i,v in enumerate(states[name]) if v['pars']==p)
                target = expected['phase_values'][key][name][index][0]
                value = values[name][label][0]
                assert_close(value,target,f'{case["case_id"]}/{key}/{name}/{label}')
                checks.append(dict(model=name,state=label,nll=value,expected_nll=target,absolute_delta=abs(value-target)))
        computed[phase] = values
        report['phases'][key] = dict(n_events=count,space_nodes=len(data['space']),time_nodes=len(data['times']),chunks=nchunks,geometry=geometry_info,input_digest=digest,original_input_digest=expected['input_digests'][key],input_digest_exact_match=digest==expected['input_digests'][key],checks=checks)
        if report_path:write(report_path,report)
        del data
    scores = []
    for name,_,_ in MODES:
        train = computed['train'][name]; test = computed['test'][name]
        original_active = fits[name]['floor_nll']-fits[name]['selected']['nll']>1.5*math.log(max(case['n_train'],1))
        active = train['floor'][0]-train['selected'][0]>1.5*math.log(max(case['n_train'],1))
        if active!=original_active:
            raise ArithmeticError('Recomputed training BIC decision changed')
        for gate in (['raw'] if name=='LI' else ['raw','BIC']):
            chosen = 'selected' if gate=='raw' or active else 'floor'
            gain = test['floor'][0]-test[chosen][0]
            row = dict(case_id=case['case_id'],regime=case['regime'],seed=case['seed'],model=name,gate=gate,gain=gain,win=gain>0,off_floor=fits[name]['selected']['pars'][0]>0 if chosen=='selected' else False,n_train=case['n_train'],n_test=case['n_test'])
            target = next(r for r in expected['results'] if (r['model'],r['gate'])==(name,gate))
            assert_close(gain,target['gain'],'held-out gain')
            if row['win']!=target['win'] or row['off_floor']!=target['off_floor']:
                raise ArithmeticError('Win/off-floor classification differs')
            scores.append(row)
    report.update(passed=True,scores=scores,elapsed_seconds=time.monotonic()-started)
    return report


def summaries(scores):
    result = []
    for regime in sorted({r['regime'] for r in scores}):
        for model,gate in [('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]:
            rows = [r for r in scores if (r['regime'],r['model'],r['gate'])==(regime,model,gate)]
            values = np.asarray([r['gain'] for r in rows]);n=len(rows);wins=sum(r['win'] for r in rows)
            p=wins/n;z=1.959963984540054;den=1+z*z/n;mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
            result.append(dict(regime=regime,model=model,gate=gate,n=n,mean_gain=float(values.mean()),median_gain=float(np.median(values)),mean_standard_error=float(values.std(ddof=1)/np.sqrt(n)) if n>1 else None,wins=wins,win_rate=p,win_wilson95=[mid-half,mid+half],off_floor=sum(r['off_floor'] for r in rows)))
    return result


def check_summary(actual,expected):
    if len(actual)!=len(expected):
        raise ValueError('Incomplete summary coverage')
    targets = {(r['regime'],r['model'],r['gate']):r for r in expected}
    for row in actual:
        target = targets[row['regime'],row['model'],row['gate']]
        for key in ('n','wins','off_floor'):
            if row[key]!=target[key]:raise ArithmeticError('Summary count differs: '+key)
        for key in ('mean_gain','median_gain','mean_standard_error','win_rate'):
            if row[key] is None or target[key] is None:
                if row[key]!=target[key]:raise ArithmeticError('Summary missing value differs')
            else:assert_close(row[key],target[key],'summary/'+key)
        for a,b in zip(row['win_wilson95'],target['win_wilson95']):assert_close(a,b,'summary/Wilson')


def generate_case(root,case,c,output):
    output.mkdir()
    rows,_,_ = c.generate(case['seed'],case['regime'],output)
    generated = read(output/'generator_receipt.json')
    original = read(resolve_input(root,case['generator_receipt']))
    digest = hashlib.sha256(np.ascontiguousarray(rows).tobytes()).hexdigest()
    exact = digest==case['rows_sha256'] and generated==original
    return dict(case_id=case['case_id'],seed=case['seed'],regime=case['regime'],passed=exact,array_digest=digest,original_array_digest=case['rows_sha256'],receipt_exact_match=generated==original,n_events=len(rows))


def validate_resources(workers,threads,chunk_mib,timeout_seconds):
    if not 1<=workers<=4 or not 1<=threads<=4 or workers*threads>4:
        raise ValueError('Require workers1..4, threads1..4 and workers*threads<=4')
    if not 16<=chunk_mib<=2048 or not math.isfinite(timeout_seconds) or timeout_seconds<=0:
        raise ValueError('Require chunk16..2048MiB and positive finite timeout')


def _score_worker_init(libraries,output,options,deadline):
    """Spawned process owns its library objects; no native handles cross IPC."""
    global _SCORE_WORKER
    c=scientific_modules()
    _SCORE_WORKER=(c,Native(libraries['cpu']),c.S.Geometry(libraries['radial']),
                   Path(output),SimpleNamespace(**options),deadline)


def _score_worker_case(case):
    c,native,geometry,output,args,deadline=_SCORE_WORKER
    path=output/(case['case_id']+'.json');started=time.monotonic()
    try:
        if time.monotonic()>deadline:raise TimeoutError('Campaign deadline reached before case')
        row=score_case(HERE,case,c,native,geometry,args,deadline,path)
    except Exception as exc:
        row=read(path) if path.is_file() else dict(case_id=case['case_id'],phases={})
        row.update(passed=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
    row['worker_pid']=os.getpid();write(path,row)
    return dict(case_id=case['case_id'],passed=row['passed'],report=path.name,worker_pid=os.getpid())


def parallel_score_cases(selected,libraries,output,args,deadline,result,
                         executor_factory=ProcessPoolExecutor,worker_function=_score_worker_case):
    """Bounded dispatch, failure retention, and original-roster result order."""
    order=[case['case_id'] for case in selected]
    if len(order)!=len(set(order)):raise ValueError('Duplicate parallel case identity')
    iterator=iter(selected);running={};completed={};started=set();stopped=False
    options=dict(threads=args.threads,chunk_mib=args.chunk_mib)
    def publish():
        result['cases']=[completed[cid] for cid in order if cid in completed]
        active=set(running.values())
        result['active_cases']=[cid for cid in order if cid in active]
        result['unstarted_cases']=[cid for cid in order if cid not in started]
        write(output/'result.json',result)
    with executor_factory(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),
                          initializer=_score_worker_init,
                          initargs=({k:str(v) for k,v in libraries.items()},str(output),options,deadline)) as pool:
        def launch():
            nonlocal stopped
            if time.monotonic()>deadline:
                stopped=True;result['stop_reason']='campaign_deadline';return False
            case=next(iterator,None)
            if case is None:return False
            cid=case['case_id']
            future=pool.submit(worker_function,case);running[future]=cid;started.add(cid)
            print(json.dumps(dict(event='case_start',case_id=cid)),flush=True)
            return True
        for _ in range(args.workers):
            if not launch():break
        publish()
        while running:
            done,_=wait(running,timeout=10,return_when=FIRST_COMPLETED)
            if not done:
                publish();continue
            for future in done:
                cid=running.pop(future)
                try:record=future.result()
                except Exception as exc:
                    path=output/(cid+'.json')
                    row=read(path) if path.is_file() else dict(case_id=cid,phases={})
                    row.update(passed=False,error_type=type(exc).__name__,error=str(exc));write(path,row)
                    record=dict(case_id=cid,passed=False,report=path.name)
                if record.get('case_id')!=cid:
                    record=dict(case_id=cid,passed=False,report=cid+'.json',error='Worker identity mismatch')
                    write(output/(cid+'.json'),record)
                completed[cid]=record
                if not record.get('passed'):
                    stopped=True;result['stop_reason']='case_failure'
                print(json.dumps(dict(event='case_complete',case_id=cid,passed=bool(record.get('passed')))),flush=True)
            publish()
            if not stopped:
                for _ in range(len(done)):
                    if not launch():break
                publish()
    publish()
    return not stopped and len(completed)==len(selected) and all(r.get('passed') for r in completed.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['score','generate','verify'],default='score')
    select = parser.add_mutually_exclusive_group()
    select.add_argument('--pilot',action='store_true',help='Four frozen first seeds, one per regime')
    select.add_argument('--case',action='append',dest='cases',help='Explicit labelled subset; may repeat')
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--workers',type=int,default=1,help='Independent score processes; workers*threads must be <=4')
    parser.add_argument('--chunk-mib',type=int,default=256)
    parser.add_argument('--timeout-seconds',type=float,default=10800)
    args = parser.parse_args(argv)
    try:validate_resources(args.workers,args.threads,args.chunk_mib,args.timeout_seconds)
    except ValueError as exc:parser.error(str(exc))
    if args.mode!='score' and args.workers!=1:
        parser.error('Multiple workers are supported only for score mode')
    output = args.output.resolve()
    if output.is_relative_to(HERE):
        parser.error('Output must be outside the immutable synthetic input bundle')
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+args.timeout_seconds
    result = dict(schema='s04b_cpu_replay_v1',passed=False,mode=args.mode,full_campaign=False,cases=[],
                  runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
                  scope='Fixed-fit score replay or explicitly selected generation witness; no optimization',tolerance_absolute=TOL,
                  resources=dict(workers=args.workers,threads_per_worker=args.threads,total_numerical_threads=args.workers*args.threads,chunk_mib_per_worker=args.chunk_mib,blas_threads_per_worker=1))
    write(output/'result.json',result)
    try:
        manifest = read(HERE/'input_manifest.json')
        result['input_manifest_sha256']=sha(HERE/'input_manifest.json')
        result['input_verification']=verify_inputs(HERE,manifest)
        roster=manifest['s04b']['cases']
        ids = manifest['s04b']['pilot_cases'] if args.pilot else args.cases
        if ids is not None and (len(set(ids))!=len(ids) or set(ids)-{r['case_id'] for r in roster}):
            raise ValueError('Unknown or duplicate selected case ID')
        selected=[r for r in roster if ids is None or r['case_id'] in ids]
        result['selected_cases']=[r['case_id'] for r in selected]
        result['requested_full_campaign']=len(selected)==80 and args.mode=='score'
        result['selection_label']='all80' if ids is None else ('fixed_four_case_pilot' if args.pilot else 'explicit_subset')
        if args.mode=='verify':
            result['passed']=True
        else:
            if args.mode=='score':
                libs=build(output/'native')
            if args.mode=='score' and args.workers>1:
                if not parallel_score_cases(selected,libs,output,args,deadline,result):
                    raise ArithmeticError('Parallel campaign incomplete or failed; retained all started-case outputs')
            else:
                c=scientific_modules()
                if args.mode=='score':native=Native(libs['cpu']);geometry=c.S.Geometry(libs['radial'])
                for case in selected:
                    if time.monotonic()>deadline:raise TimeoutError('Campaign deadline reached')
                    result['active_case']=case['case_id']
                    write(output/'result.json',result)
                    print(json.dumps(dict(event='case_start',case_id=case['case_id'])),flush=True)
                    row = score_case(HERE,case,c,native,geometry,args,deadline,output/(case['case_id']+'.json')) if args.mode=='score' else generate_case(HERE,case,c,output/case['case_id'])
                    write(output/(case['case_id']+'.json'),row)
                    result['cases'].append(dict(case_id=case['case_id'],passed=row['passed'],report=case['case_id']+'.json'))
                    write(output/'result.json',result)
                    if not row['passed']:raise ArithmeticError('Case failed exact reproduction')
                    print(json.dumps(dict(event='case_complete',case_id=case['case_id'],passed=True)),flush=True)
            if args.mode=='score':
                scores=[r for case in result['cases'] for r in read(output/case['report'])['scores']]
                summary=summaries(scores)
                if len(selected)==80:
                    expected=read(resolve_input(HERE,manifest['s04b']['expected_summary']))
                else:
                    old=[dict(regime=case['regime'],**r) for case in selected for r in read(resolve_input(HERE,case['expected']))['results']]
                    expected=summaries(old)
                check_summary(summary,expected)
                write(output/'scores.json',scores);write(output/'summary.json',summary)
            result['passed']=True
            result['full_campaign']=result['requested_full_campaign']
            result.pop('active_case',None)
    except Exception as exc:
        result.update(error_type=type(exc).__name__,error=str(exc))
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        write(output/'result.json',result)
    print(json.dumps({k:result[k] for k in ['passed','mode','full_campaign','elapsed_seconds']}),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
