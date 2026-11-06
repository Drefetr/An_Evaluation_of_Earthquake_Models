"""Reconstruct the fixed S2 histories and their paired uninhibited histories.

No likelihood, optimizer, native library or replacement seed is used.
"""
import argparse,dataclasses,hashlib,importlib.util,json,math,os,platform,shutil,sys,time
from pathlib import Path
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[name]='1'
import numpy as np
HERE=Path(__file__).resolve().parent
MANIFEST_SHA='12e9f19dc0d1ac9ad48d20908b0a7209432f7c53c3a3e8e2ab8ba82a1aab126f'
PROTOCOL_SHA='ba8db1f4036d6423622ee4f6b0f4f1c4c2ef9a9a60e95cfc577e19ce2f5eb84a'
SEEDS=list(range(410201,410221))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    temporary=Path(p).with_suffix(Path(p).suffix+'.tmp')
    with temporary.open('x',encoding='utf-8')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
    os.replace(temporary,p)
def need(ok,message):
    if not ok:raise ValueError(message)
def safe(root,relative):
    p=(root/relative).resolve();need(not Path(relative).is_absolute()and p.is_relative_to(root.resolve()),'Path escapes input root');return p
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def rows_of(events):return np.asarray([[e.time,e.x,e.y,e.Q]for e in events],dtype=np.float64).reshape(-1,4)
def compare_rows(actual,expected):
    need(actual.shape==expected.shape and actual.ndim==2 and actual.shape[1]==4,'History shape/order mismatch')
    need(actual.dtype==expected.dtype==np.dtype('float64'),'History dtype mismatch')
    need(np.isfinite(actual).all()and np.isfinite(expected).all()and np.all(actual>=0)and np.all(expected>=0),'Nonfinite/negative history field')
    need(np.all(np.diff(actual[:,0])>=0)and np.all(np.diff(expected[:,0])>=0),'History order changed')
    delta=np.abs(actual-expected);maximum=delta.max(axis=0).tolist()if len(actual)else[0.]*4
    ulp=np.abs(actual.view(np.int64)-expected.view(np.int64))
    result=dict(exact_float64_bytes=actual.tobytes()==expected.tobytes(),maximum_absolute_difference=maximum,
                maximum_ulp_distance=ulp.max(axis=0).tolist()if len(actual)else[0]*4,
                differing_scalar_fields=int(np.sum(actual!=expected)),absolute_tolerance=1e-9,relative_tolerance=0.)
    need(all(x<=1e-9 for x in maximum),'Historical row discrepancy exceeds frozen tolerance')
    return result
def verify_inputs():
    need(sha(HERE/'manifest.json')==MANIFEST_SHA and sha(HERE/'protocol.json')==PROTOCOL_SHA,'Frozen manifest/protocol changed')
    manifest=read(HERE/'manifest.json');protocol=read(HERE/'protocol.json')
    need(protocol['manifest_sha256']==MANIFEST_SHA,'Protocol manifest binding changed')
    need([c['seed']for c in manifest['cases']]==SEEDS,'Fixed20 seed roster changed')
    need(sum(c['events']for c in manifest['cases'])==4268,'Original event denominator changed')
    need(len({r['path']for r in manifest['files']})==len(manifest['files']),'Duplicate input path')
    for row in manifest['files']:
        p=safe(HERE,row['path']);need(p.stat().st_size==row['bytes']and sha(p)==row['sha256'],'Input hash mismatch: '+row['path'])
    for case in manifest['cases']:
        with np.load(safe(HERE,case['history']),allow_pickle=False)as z:rows=z['rows']
        need(rows.shape==(case['events'],4)and rows.dtype==np.dtype('float64'),'Original array shape/dtype')
        need(hashlib.sha256(rows.tobytes()).hexdigest()==case['rows_sha256'],'Original array digest')
        compare_rows(rows,rows)
    source=HERE.parent/'source/generator.py'
    need(sha(source)==protocol['public_generator_sha256']==manifest['public_generator_sha256'],'Public generator changed')
    return manifest,protocol,source
def load_generator(source):
    spec=importlib.util.spec_from_file_location('_s2_pinned_generator',source);module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def rng_common(actual,expected):
    for key in ('raw_uniform_words','open_uniforms','stream_state_sha256'):
        need(all(actual[key][str(i)]==expected[key][str(i)]for i in range(7)),'RNG common-stream mismatch: '+key)
    need(actual['poisson_calls']==expected['poisson_calls'],'RNG Poisson call mismatch')
    need(actual['raw_uniform_words']['7']==actual['open_uniforms']['7']==0,'Unused stream7 advanced')
def simulate(g,seed,eta,folder,deadline,on_call):
    folder.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    result=dict(seed=seed,eta=eta,passed=False)
    try:
        law=g.Law('S2_narrow_short',seed,'smooth',eta,5.,1/24);limits=g.Limits()
        remaining=min(30.,deadline-began);need(remaining>0,'Phase deadline expired before simulation')
        budget=g.Budget(limits,deadline_after=remaining);streams=g.ScalarStreams(seed,limits,budget);sim=g._Simulator(law,limits,budget,streams)
    except BaseException as exc:
        result.update(error_type=type(exc).__name__,error=str(exc),wall_seconds=time.monotonic()-began);write(folder/'run.json',result);raise
    observer=dict(accepted=0,rejected=0,minimum_signed_margin=None,minimum_absolute_margin=None)
    original_uniform=streams.uniform
    def uniform(code):
        u=original_uniform(code)
        if code==3:
            entry=sim.batch_journal[-1];t=entry['candidate']['time']
            stress=g.strict_stress(t,entry['x_km'],entry['y_km'],sim.history,law.ell,law.psi)
            threshold=math.exp(-law.eta*stress);margin=threshold-u
            need(math.isfinite(margin),'Nonfinite acceptance margin')
            observer['accepted'if u<threshold else'rejected']+=1
            observer['minimum_signed_margin']=margin if observer['minimum_signed_margin']is None else min(observer['minimum_signed_margin'],margin)
            observer['minimum_absolute_margin']=abs(margin)if observer['minimum_absolute_margin']is None else min(observer['minimum_absolute_margin'],abs(margin))
        return u
    streams.uniform=uniform
    result.update(law=dataclasses.asdict(law),limits=dataclasses.asdict(limits),operational_deadline_seconds=remaining)
    try:
        on_call();sim.run();need(not sim.queue and not sim.pending_uncommitted,'Incomplete horizon')
        counts=dataclasses.asdict(sim.counts)
        need(observer['accepted']==counts['accepted_immigrants']and observer['rejected']==counts['rejected_immigrants'],'Acceptance observer differs from actual counters')
        need(counts['accepted_committed']==len(sim.history)==counts['accepted_immigrants']+counts['accepted_offspring'],'Accepted-count mismatch')
        need(counts['queue_created']==counts['queue_processed']==len(sim.history)+counts['rejected_immigrants']+counts['rejected_offspring'],'Queue-accounting mismatch')
        result['passed']=True
    except BaseException as exc:result.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:
        rows=rows_of(sim.history);np.savez_compressed(folder/'history.npz',rows=rows)
        records=[g._event_record(e)for e in sim.history]
        with (folder/'events.jsonl').open('x',encoding='utf-8')as f:
            for record in records:f.write(canonical(record).decode()+'\n')
        result.update(counters=dataclasses.asdict(sim.counts),rng=streams.snapshot(),observer=observer,
                      events=len(rows),rows_sha256=hashlib.sha256(rows.tobytes()).hexdigest(),event_records_sha256=hashlib.sha256(canonical(records)).hexdigest(),
                      history_file_sha256=sha(folder/'history.npz'),events_file_sha256=sha(folder/'events.jsonl'),wall_seconds=time.monotonic()-began)
        write(folder/'run.json',result)
    return result,rows,records
def pair(g,case,folder,deadline,on_call):
    folder.mkdir(parents=True,exist_ok=False);report=dict(seed=case['seed'],passed=False)
    write(folder/'case.json',report)
    try:
        positive,rows,records=simulate(g,case['seed'],.5,folder/'positive',deadline,on_call)
        with np.load(safe(HERE,case['history']),allow_pickle=False)as z:expected=z['rows']
        report['original_s04_comparison']=compare_rows(rows,expected)
        if 'initial_receipt'in case:
            receipt=read(safe(HERE,case['initial_receipt']))
            need(all(positive['counters'][k]==v for k,v in receipt['counters'].items()),'Original common counters changed')
            rng_common(positive['rng'],receipt['rng_counters_and_state_hashes'])
            initial=[json.loads(line)for line in safe(HERE,case['initial_events']).read_text(encoding='utf-8').splitlines()]
            oldrows=np.asarray([[e['time_days'],e['x_km'],e['y_km'],e['Q']]for e in initial],dtype=np.float64)
            report['initial_jsonl_comparison']=compare_rows(rows,oldrows)
            numeric={'time_days','x_km','y_km','Q'}
            need([{k:v for k,v in e.items()if k not in numeric}for e in records]==[{k:v for k,v in e.items()if k not in numeric}for e in initial],'Initial event ancestry/partition/order changed')
            report['initial_counters_rng_and_ancestry_exact']=True
        null,nullrows,nullrecords=simulate(g,case['seed'],0.,folder/'null',deadline,on_call)
        zero=positive['counters']['rejected_immigrants']+positive['counters']['rejected_offspring']==0
        coupling=dict(zero_rejection=zero,exact_float64_bytes=rows.shape==nullrows.shape and rows.tobytes()==nullrows.tobytes(),
                      exact_event_records=canonical(records)==canonical(nullrecords))
        if zero:
            need(coupling['exact_float64_bytes']and coupling['exact_event_records'],'Zero-rejection coupling mismatch')
            rng_common(positive['rng'],null['rng'])
        coupling['common_rng_exact']=all(positive['rng'][k][str(i)]==null['rng'][k][str(i)]for k in ('raw_uniform_words','open_uniforms','stream_state_sha256')for i in range(7))and positive['rng']['poisson_calls']==null['rng']['poisson_calls']
        report.update(passed=True,counters=positive['counters'],coupling=coupling,positive_run_sha256=sha(folder/'positive/run.json'),null_run_sha256=sha(folder/'null/run.json'))
    except BaseException as exc:report.update(error_type=type(exc).__name__,error=str(exc));raise
    finally:write(folder/'case.json',report)
    return report
def summary(cases):
    need(sorted(c['seed']for c in cases)==SEEDS and all(c['passed']for c in cases),'Cannot summarize incomplete fixed20 roster')
    total=lambda key:sum(c['counters'][key]for c in cases)
    return dict(case_count=20,zero_rejection_histories=sum(c['coupling']['zero_rejection']for c in cases),
                proposed_immigrants=total('accepted_immigrants')+total('rejected_immigrants'),rejected_immigrants=total('rejected_immigrants'),
                proposed_offspring=total('accepted_offspring')+total('rejected_offspring'),rejected_offspring=total('rejected_offspring'),total_events=total('accepted_committed'))
def run(args):
    out=Path(args.output).resolve();need(not out.is_relative_to(HERE),'Output must be outside the package');out.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();result=dict(phase=args.phase,passed=False,cases=[],new_simulation_calls=0,reused_simulation_calls=0)
    write(out/'result.json',result)
    try:
        manifest,protocol,source=verify_inputs()
        identity=dict(script_sha256=sha(__file__),manifest_sha256=MANIFEST_SHA,protocol_sha256=PROTOCOL_SHA,generator_sha256=sha(source))
        g=load_generator(source);result.update(identity=identity,runtime=g.runtime_fingerprint())
        cases=[];records=[];prior_seconds=0.
        selected=[c for c in manifest['cases']if c['seed']in(410201,410202)]if args.phase=='pilot'else manifest['cases']
        if args.phase=='full':
            need(args.pilot is not None,'Full phase requires the exact two-case pilot');root=Path(args.pilot).resolve();pilot=read(root/'result.json')
            need(pilot.get('passed')and pilot['phase']=='pilot'and pilot['identity']==identity and pilot['runtime']==result['runtime'],'Pilot did not pass under identical source/input/runtime')
            for record in pilot['cases']:
                p=safe(root,record['file']);need(sha(p)==record['sha256'],'Pilot case changed');case=read(p)
                need(case['passed']and case['seed']in(410201,410202),'Invalid pilot case');cases.append(case)
                need(p==root/str(case['seed'])/'case.json','Unexpected pilot record path')
                for law in ('positive','null'):
                    record_path=p.parent/law/'run.json';need(sha(record_path)==case[law+'_run_sha256'],'Pilot run changed')
                    run_record=read(record_path);need(run_record['passed']and run_record['seed']==case['seed'],'Incomplete pilot simulation')
                    need(sha(p.parent/law/'history.npz')==run_record['history_file_sha256'],'Pilot history changed')
                    need(sha(p.parent/law/'events.jsonl')==run_record['events_file_sha256'],'Pilot event records changed')
                target=out/f"{case['seed']}";shutil.copytree(p.parent,target)
                result['reused_simulation_calls']+=2
                records.append(dict(seed=case['seed'],file=f"{case['seed']}/case.json",sha256=sha(target/'case.json'),source='exact pilot reuse',original_file_sha256=record['sha256']))
            need(sorted(c['seed']for c in cases)==[410201,410202],'Pilot fixed roster incomplete')
            prior_seconds=pilot['wall_seconds'];result['pilot_result_sha256']=sha(root/'result.json')
            selected=[c for c in manifest['cases']if c['seed']not in(410201,410202)]
        cap=120 if args.phase=='pilot'else 1200-prior_seconds;need(math.isfinite(cap)and cap>0,'Campaign budget exhausted');deadline=began+cap
        def on_call():
            result['new_simulation_calls']+=1;write(out/'result.json',result)
        for case in selected:
            need(time.monotonic()<deadline,'Phase wall cap reached');result['active_seed']=case['seed'];write(out/'result.json',result)
            try:report=pair(g,case,out/str(case['seed']),deadline,on_call)
            finally:
                case_path=out/str(case['seed'])/'case.json'
                if case_path.is_file():records.append(dict(seed=case['seed'],file=f"{case['seed']}/case.json",sha256=sha(case_path),source='new paired reconstruction'))
                result['cases']=records;write(out/'result.json',result)
            cases.append(report)
        need(len(cases)==(2 if args.phase=='pilot'else 20)and time.monotonic()<deadline,'Required phase incomplete or over deadline')
        if args.phase=='full':
            value=summary(cases);need(value['total_events']==4268,'Original total event count mismatch');write(out/'summary.json',value);result['summary_sha256']=sha(out/'summary.json')
            if args.check_summary:need((out/'summary.json').read_bytes()==Path(args.check_summary).read_bytes(),'Deterministic summary differs')
        result.update(passed=True,cases=records,wall_seconds=time.monotonic()-began,cumulative_wall_seconds=prior_seconds+time.monotonic()-began);result.pop('active_seed',None)
    except BaseException as exc:result.update(passed=False,error_type=type(exc).__name__,error=str(exc),wall_seconds=time.monotonic()-began)
    write(out/'result.json',result);return 0 if result['passed']else 1
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['pilot','full'],required=True);p.add_argument('--output',required=True);p.add_argument('--pilot');p.add_argument('--check-summary');return run(p.parse_args())
if __name__=='__main__':raise SystemExit(main())
