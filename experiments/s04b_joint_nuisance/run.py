"""Frozen-roster joint background/temporal fits; reviewed admission required."""
from __future__ import annotations
import argparse,datetime,gc,hashlib,json,math,os,platform,shutil,sys,time
from pathlib import Path
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key]='2'
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
sys.path.insert(0,str(REPO))
import numpy as np
import scipy
from threadpoolctl import threadpool_limits,threadpool_info
from experiments.s04b_joint_nuisance import model, checkpoint as persistence
from experiments.s04b_joint_nuisance.fit import MODELS,bounds,boundary,fit_arm,fine_check

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON '+v)))
def sha(path):
    with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
write=persistence.write
def require(value,message):
    if not value:raise ValueError(message)
def close(a,b,tol,label):
    require(math.isfinite(a)and math.isfinite(b)and abs(a-b)<=tol,label+f': {a}, {b}, tol={tol}')
def source_identity():
    return {p.name:sha(p)for p in sorted(HERE.iterdir())if p.is_file()and p.suffix in('.py','.cpp','.json')}
def runtime_identity():
    import numpy._core._multiarray_umath as array_engine
    import scipy.optimize._lbfgsb as optimizer_engine
    return dict(essential=dict(python_version=platform.python_version(),implementation=platform.python_implementation(),
        python_executable_sha256=sha(sys.executable),numpy=np.__version__,scipy=scipy.__version__,architecture=platform.machine(),
        byteorder=sys.byteorder,numpy_extension_sha256=sha(array_engine.__file__),lbfgsb_extension_sha256=sha(optimizer_engine.__file__),
        numerical_libraries=sorted([dict(api=v['internal_api'],version=v['version'],sha256=sha(v['filepath']))for v in threadpool_info()],key=lambda v:(v['api'],v['sha256']))),
        metadata=dict(python_build=sys.version,platform=platform.platform()))
def safe(root,relative):
    p=(root/relative).resolve();require(not Path(relative).is_absolute()and p.is_relative_to(root.resolve()),'Escaping path');return p
def verify_inputs(protocol):
    require(sha(HERE/'input_pins.json')==protocol['input_pins_sha256'],'Input pin document changed')
    for relative,expected in read(HERE/'input_pins.json').items():require(sha(safe(REPO,relative))==expected,'Input changed: '+relative)
    manifest=read(REPO/'reproduction/synthetic/input_manifest.json');cases=sorted(manifest['s04b']['cases'],key=lambda c:(c['regime'],c['seed']))
    require([c['case_id']for c in cases]==protocol['roster']and len(cases)==80,'Fixed80 roster changed')
    for c in cases:
        with np.load(REPO/'reproduction/synthetic'/c['history'],allow_pickle=False)as z:rows=z['rows']
        require(rows.ndim==2 and rows.shape[1]==4 and np.isfinite(rows).all()and np.all(np.diff(rows[:,0])>=0),'Invalid history')
        require(hashlib.sha256(rows.tobytes()).hexdigest()==c['rows_sha256'],'History array identity changed')
        require(np.all((rows[:,0]>=0)&(rows[:,0]<760))and np.all(rows[:,3]>=0),'History outside law')
        c['parents_train']=int(np.sum(rows[:,0]<395));c['parents_test']=len(rows)
        for phase,start,end in [('train',30,395),('test',395,760)]:require(int(np.sum((rows[:,0]>=start)&(rows[:,0]<end)))==c['n_'+phase],'Phase denominator changed')
    return cases

def historical_floor(phase,case,old,expected,states,fits,label):
    theta=[math.log(.2),.2,.35,math.log(.05),1.3,0.,math.log(30),math.log(7)]
    score,_=phase.evaluate(theta,'null');checks=[]
    order=16 if label=='train'else 32
    for name in MODELS:
        index=next(i for i,v in enumerate(states[name])if v['pars']==fits[name]['floor'])
        row=expected['phase_values'][f'order{order}_{label}'][name][index]
        close(score['nll'],float(row[0]),1e-9,'Identical historical phase/model floor')
        close(score['P'],float(row[5]),1e-9,'Identical historical point sum')
        checks.append(dict(phase=label,model=name,actual_nll=score['nll'],expected_nll=row[0],absolute_delta=abs(score['nll']-row[0]),tolerance=1e-9))
    for key in ('P','E','C','M','joint'):close(score[key],old['phases'][label]['historical'][key],1e-9,'Full-precision historical floor '+key)
    return score,checks

def compare_historical(case,old,expected,states,fits):
    rows=[]
    required={(name,gate)for name in MODELS for gate in(('raw',)if name=='LI'else('raw','BIC'))}
    require(len(old['outcomes'])==5 and {(r['model'],r['gate'])for r in old['outcomes']}==required,'Historical five-procedure roster changed')
    for original in old['outcomes']:
        name,gate=original['model'],original['gate'];matched=next(r for r in expected['results']if(r['model'],r['gate'])==(name,gate))
        require(original['selected_state_index']==matched['selected_state_index'],'Historical selected state changed')
        selected=expected['phase_values']['order32_test'][name][matched['selected_state_index']]
        score=-float(selected[0]);floor=original['original_floor_test_joint'];intercept=old['phases']['test']['refitted']['joint']
        close(score,original['saved_procedure_test_joint'],1e-9,'Historical procedure joint')
        close(score-floor,original['original_gain'],1e-9,'Historical fixed-floor gain')
        close(score-intercept,original['new_gain'],1e-9,'Historical intercept-floor gain')
        close(original['original_gain'],matched['gain'],1e-9,'Historical archive gain')
        rows.append(dict(model=name,gate=gate,fixed_floor_gain=original['original_gain'],intercept_only_gain=original['new_gain'],
                         saved_procedure_joint=score,fixed_floor_joint=floor,intercept_floor_joint=intercept,
                         historical_off_floor=original['original_off_floor'],selected_state_index=matched['selected_state_index'],passed=True))
    require(len(rows)==5,'Five historical comparison rows required');return rows

def select_prediction(fitted,gate,gate_active,null_parameters,null_score,raw_score):
    floor=fitted['selected']['kind']=='new_null_floor'or(gate=='BIC'and not gate_active)
    score=null_score if floor else raw_score
    gain=0. if floor else score['joint']-null_score['joint']
    return dict(parameters=null_parameters if floor else fitted['selected']['parameters'],score=score,
                floor_return=floor,selected_state_index=0 if floor else fitted['selected_state_index'],
                new_gain=gain,new_win=gain>0,near_zero=abs(gain)<=1e-9,
                robust_positive=gain>1e-9,robust_negative=gain< -1e-9)

def load_training_resume(args,a,current,out):
    """Admit only the independently reviewed immutable first failed checkpoint."""
    policy=read(HERE/'checkpoint_repair.json');root=Path(args.resume_training).resolve()
    require(args.resume_review and args.resume_archive,'Resume requires original archive and independent review')
    grant=a.get('training_resume',{})
    require(grant.get('independent_review_passed')is True,'No reviewed training-resume admission')
    paths={'failed_result_sha256':root/'result.json','checkpoint_sha256':root/(policy['case_id']+'.json'),
           'attempts_sha256':root/(policy['case_id']+'.attempts.jsonl'),
           'failed_archive_sha256':Path(args.resume_archive),'audit_sha256':Path(args.resume_review)}
    for key,path in paths.items():require(sha(path)==policy[key]==grant.get(key),'Resume evidence changed: '+key)
    require(sha(HERE/'pre_repair_source.zip')==policy['source_archive_sha256'],'Predecessor source archive changed')
    previous=read(paths['failed_result_sha256']);audit=read(paths['audit_sha256'])
    require(audit['passed']is True and not audit['scientific_pilot_passed'],'Partial-checkpoint audit status changed')
    require(previous['passed']is False and previous['phase']=='pilot'and not previous['cases'],'Not the frozen failed pilot')
    require(previous['source_sha256']==policy['predecessor_source_sha256'],'Predecessor source map changed')
    for name,expected in previous['source_sha256'].items():
        if name!='run.py':require(sha(HERE/name)==expected,'Resume mathematical source/protocol/input changed: '+name)
    require(previous['runtime']['essential']==current['runtime']['essential'],'Resume essential runtime changed')
    require(previous['library_sha256']==current['library_sha256']and previous['build_receipt_sha256']==current['build_receipt_sha256'],'Resume native/build identity changed')
    require(previous['wall_seconds']==policy['prior_scientific_seconds'],'Prior elapsed time changed')
    checkpoint=read(paths['checkpoint_sha256'])
    persistence.validate_training(checkpoint,paths['attempts_sha256'],policy)
    for relative,expected in checkpoint['input_sha256'].items():
        base=REPO if relative.startswith('validation/')else REPO/'reproduction/synthetic'
        require(sha(safe(base,relative))==expected,'Resume case input changed: '+relative)
    dest=out/'training_resume';dest.mkdir(exist_ok=False)
    names={'failed_result_sha256':'failed_result.json','checkpoint_sha256':'frozen_training.json',
           'attempts_sha256':'frozen_training.attempts.jsonl','audit_sha256':'independent_partial_review.json',
           'failed_archive_sha256':'failed_pilot_original.zip'}
    for key,path in paths.items():shutil.copy2(path,dest/names[key])
    provenance=dict(case_id=policy['case_id'],**{k:policy[k]for k in paths},
        predecessor_source_sha256=previous['source_sha256'],predecessor_runtime=previous['runtime'],
        prior_scientific_seconds=previous['wall_seconds'],prior_supervised_seconds=policy['prior_supervised_seconds'],
        training_payload_canonical_sha256=policy['training_payload_canonical_sha256'],
        evidence_files={k:'training_resume/'+name for k,name in names.items()},
        reused_fit_arms=4,repeated_training_evaluations=0,scope='Exact frozen training; only missing test scoring is executed')
    write(dest/'provenance.json',provenance)
    return dict(case_id=policy['case_id'],checkpoint=dest/names['checkpoint_sha256'],
                trace=dest/names['attempts_sha256'],prior_seconds=previous['wall_seconds'],provenance=provenance)

def case_run(case,modules,native,protocol,out,deadline,resume=None):
    started=time.monotonic();path=out/(case['case_id']+'.json');trace=out/(case['case_id']+'.attempts.jsonl')
    report=dict(case_id=case['case_id'],regime=case['regime'],seed=case['seed'],passed=False,status='running',fits={},floor_checks=[],outcomes=[])
    if resume is not None:
        report=read(resume['checkpoint']);report.update(passed=False,status='resuming_test',outcomes=[],resume_provenance=resume['provenance'])
        shutil.copy2(resume['trace'],trace)
    write(path,report)
    def checkpoint(record):
        with trace.open('a',encoding='utf-8')as f:f.write(persistence.dumps(record)+'\n');f.flush();os.fsync(f.fileno())
    try:
        root=REPO/'reproduction/synthetic'
        with np.load(root/case['history'],allow_pickle=False)as z:rows=z['rows'].copy()
        fits={k:read(root/v)for k,v in case['fits'].items()};states=read(root/case['states']);expected=read(root/case['expected'])
        old_path=REPO/'validation/live_results/methodological_20261106/refitted_floor'/(case['case_id']+'.json');old=read(old_path)
        G=modules['generator'];name=G.MATCHED_NAMES[case['regime']-4];_,bg,eta,ell,psi=G.ROSTER[name]
        law=G.Law(name,case['seed'],bg,eta,ell,psi);gm=G.fitting_metadata(law)
        report.update(fixed_spatial_mark_law=dict(**gm,productivity_ratio_r=law.r,spatial_kernel_exponent=2),input_sha256={case['history']:sha(root/case['history']),case['generator_receipt']:sha(root/case['generator_receipt']),
                      case['expected']:sha(root/case['expected']),str(old_path.relative_to(REPO)).replace('\\','/'):sha(old_path)},
                      n_train=case['n_train'],n_test=case['n_test'],thinning=read(root/case['generator_receipt'])['counters'],
                      stratum='count-suppressed/weak-geometry'if case['regime']in(5,7)else'narrow-short')
        report['historical_comparisons']=compare_historical(case,old,expected,states,fits)
        if resume is None:
            train=model.phase_from_rows(rows,gm,30,395,modules,native,deadline)
            historical,checks=historical_floor(train,case,old,expected,states,fits,'train');report['floor_checks']+=checks
            initial=np.array([law.a,law.d,law.n,math.log(law.c),law.p,0.,math.log(30.),math.log(7.)])
            null=fit_arm(train,'null',protocol,initial,checkpoint);report['fits']['null']=null;write(path,report)
            require(null['passed'],'Unresolved null starts')
            nc=fine_check(train,'null',null,protocol);report['training_checks']={'null':nc};require(nc['passed'],'Null quadrature check')
            selected_null=null['selected']['parameters'];close(nc['coarse']['joint'],nc['fine']['joint'],1e-9,'Null exact functional')
            require(nc['fine']['nll']<=historical['nll']+1e-9,'New null worsens feasible historical floor')
            for name in MODELS:
                arm=fit_arm(train,name,protocol,selected_null,checkpoint);report['fits'][name]=arm;write(path,report)
                require(arm['passed'],'Unresolved alternative starts')
                check=fine_check(train,name,arm,protocol);report['training_checks'][name]=check;write(path,report)
                require(check['passed'],'Selected training quadrature/gradient check')
                require(check['fine']['nll']<=nc['fine']['nll']+1e-9,'Selected alternative worsens eligible new null at verified order')
            report['plan_dimensions']={'train':{str(o):{k:g[k]for k in('space_nodes','time_nodes','parents','estimate')}for o,g in train._grids.items()}}
            report['training_selections_frozen']=True;write(path,report);del train;gc.collect()
        else:
            require(report['input_sha256']==read(resume['checkpoint'])['input_sha256'],'Resume inputs changed')
            persistence.validate_training(report,trace,read(HERE/'checkpoint_repair.json'))
            nc=report['training_checks']['null'];selected_null=report['fits']['null']['selected']['parameters']
        test=model.phase_from_rows(rows,gm,395,760,modules,native,deadline)
        _,checks=historical_floor(test,case,old,expected,states,fits,'test');report['floor_checks']+=checks
        null_test=test.evaluate(selected_null,'null',16)[0];report['new_null_test']=null_test
        threshold=1.5*math.log(max(case['n_train'],1));report['bic_threshold']=threshold
        for name in MODELS:
            fitted=report['fits'][name];theta=fitted['selected']['parameters'];raw=test.evaluate(theta,name,16)[0]
            coarse=test.evaluate(theta,name,8)[0];close(raw['joint'],coarse['joint'],1e-4,'Selected held-out quadrature')
            require(raw['E']>=0,'Selected held-out exposure is numerically negative')
            report.setdefault('test_checks',{})[name]=dict(fine=raw,coarse=coarse,absolute_joint_delta=abs(raw['joint']-coarse['joint']))
            train_gain=nc['fine']['nll']-report['training_checks'][name]['fine']['nll']
            coarse_train_gain=nc['coarse']['nll']-report['training_checks'][name]['coarse']['nll']
            gate_active=train_gain>threshold
            for gate in(('raw',)if name=='LI'else('raw','BIC')):
                prediction=select_prediction(fitted,gate,gate_active,selected_null,null_test,raw)
                chosen=prediction['parameters'];score=prediction['score'];gain=prediction['new_gain']
                delta={k:score[k]-null_test[k]for k in('P','E','C','M','joint')}
                if prediction['floor_return']:delta={k:0. for k in delta}
                close(gain,delta['P']+delta['C']+delta['M'],1e-9,'New signed component identity')
                require(delta['M']==0 and delta['C']==-delta['E'],'Common marks or signed exposure changed')
                oldrow=next(v for v in report['historical_comparisons']if(v['model'],v['gate'])==(name,gate))
                report['outcomes'].append(dict(model=name,gate=gate,**prediction,new_null_score=null_test,delta=delta,
                    off_floor=chosen[5]>0,
                    training_gain=train_gain,coarse_training_gain=coarse_train_gain,gate_active=gate_active,
                    fine_threshold_distance=train_gain-threshold,coarse_threshold_distance=coarse_train_gain-threshold,
                    coarse_fine_gate_disagreement=(coarse_train_gain>threshold)!=gate_active,
                    gate_uses='fine training scores at coarse-selected verified states',
                    null_search_gap_detected=bool(fitted['null_search_gaps']),
                    gain_interpretation='Joint fitted-procedure contrast; null-search gap prevents attribution to inhibition'if fitted['null_search_gaps']else'Joint fitted-procedure contrast, not detection or physical inhibition',
                    boundaries=boundary(chosen,protocol['shared_bounds']+protocol['inhibition_bounds']),historical=oldrow,
                    saved_procedure_vs_new_null=oldrow['saved_procedure_joint']-null_test['joint']))
        report['plan_dimensions']['test']={str(o):{k:g[k]for k in('space_nodes','time_nodes','parents','estimate')}for o,g in test._grids.items()}
        require(len(report['outcomes'])==5 and len(report['floor_checks'])==6,'Case roster incomplete')
        if resume is not None:
            frozen=read(resume['checkpoint']);current={k:report[k]for k in frozen if k not in('passed','status','outcomes')}
            current['floor_checks']=[v for v in report['floor_checks']if v['phase']=='train']
            current['plan_dimensions']={'train':report['plan_dimensions']['train']}
            require(persistence.canonical_training(current,read(HERE/'checkpoint_repair.json')['training_payload_keys'])==persistence.canonical_training(frozen,read(HERE/'checkpoint_repair.json')['training_payload_keys']),'Frozen training was changed during test completion')
            require(sha(trace)==resume['provenance']['attempts_sha256'],'Resume appended or changed original training trace')
        report.update(passed=True,status='complete');del test;gc.collect()
    except BaseException as exc:report.update(passed=False,status='unknown',error_type=type(exc).__name__,error=str(exc))
    finally:
        report['current_attempt_wall_seconds']=time.monotonic()-started
        report['prior_training_attempt_seconds']=0. if resume is None else resume['prior_seconds']
        report['wall_seconds']=report['current_attempt_wall_seconds']+report['prior_training_attempt_seconds']
        if trace.exists():report['attempts_sha256']=sha(trace)
        try:write(path,report)
        except BaseException as exc:
            write(out/(case['case_id']+'.persistence_failure.json'),dict(passed=False,status='checkpoint_write_failed',
                error_type=type(exc).__name__,error=str(exc),last_durable_checkpoint_sha256=sha(path)if path.exists()else None))
            raise
    return report

def wilson(wins,N):
    z=1.959963984540054;p=wins/N;den=1+z*z/N
    center=(p+z*z/(2*N))/den;half=z*math.sqrt(p*(1-p)/N+z*z/(4*N*N))/den
    return [max(0.,center-half),min(1.,center+half)]
def aggregate(reports,protocol):
    require(sorted(r['case_id']for r in reports)==sorted(protocol['roster'])and all(r['passed']for r in reports),'Complete80 reports required')
    result=[]
    for regime in range(4,8):
        group=[r for r in reports if r['regime']==regime];require(len(group)==20,'Twenty histories per regime required')
        for name in MODELS:
            for gate in(('raw',)if name=='LI'else('raw','BIC')):
                rows=[next(v for v in r['outcomes']if(v['model'],v['gate'])==(name,gate))for r in group]
                gains=[v['new_gain']for v in rows];wins=sum(v['new_win']for v in rows)
                result.append(dict(regime=regime,model=name,gate=gate,N=20,mean_gain=math.fsum(gains)/20,median_gain=float(np.median(gains)),
                    wins=wins,wilson95=wilson(wins,20),wilson_scope='pointwise bounded-win interval, not simultaneous or mean-gain inference',
                    near_zero=sum(v['near_zero']for v in rows),positive_near_zero=sum(v['near_zero']and v['new_win']for v in rows),
                    robust_positive=sum(v['robust_positive']for v in rows),robust_negative=sum(v['robust_negative']for v in rows),
                    off_floor=sum(v['off_floor']for v in rows),floor_returns=sum(v['floor_return']for v in rows),unknowns=0,
                    a_boundary=sum(v['boundaries'][0]is not None for v in rows),eta_lower=sum(v['boundaries'][5]=='lower'for v in rows),
                    eta_upper=sum(v['boundaries'][5]=='upper'for v in rows),null_search_gap_cases=sum(bool(r['fits'][name]['null_search_gaps'])for r in group),
                    coarse_fine_gate_disagreements=sum(v['coarse_fine_gate_disagreement']for v in rows),
                    optimizer_failed_attempts=sum(not v['success']for r in group for arm in('null',name)for v in r['fits'][arm]['records']),
                    coordinate_boundaries={coordinate:{side:sum(v['boundaries'][i]==side for v in rows)for side in('lower','upper')}for i,coordinate in enumerate(protocol['coordinates'])},
                    realized_thinning={key:sum(r['thinning'][key]for r in group)for key in('accepted_immigrants','rejected_immigrants','accepted_offspring','rejected_offspring')},
                    mean_training_events=sum(r['n_train']for r in group)/20,mean_test_events=sum(r['n_test']for r in group)/20,
                    primary=(regime,name,gate)in((5,'LIplus_immigrant','raw'),(7,'LIplus_inclusive','raw'))))
    return result

def admission(args,protocol):
    a=read(args.admission);now=datetime.datetime.now(datetime.timezone.utc)
    require(a['phase']==args.phase and a['independent_review_passed']is True,'Unreviewed phase admission')
    require(datetime.datetime.fromisoformat(a['expires_utc'])>now,'Expired numerical admission')
    require(a['source_sha256']==source_identity(),'Reviewed source identity changed')
    require(a['protocol_sha256']==sha(HERE/'protocol.json')and a['input_pins_sha256']==sha(HERE/'input_pins.json'),'Reviewed protocol identity changed')
    token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','');require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'],'Numerical lease attestation mismatch')
    build=read(args.build_receipt)
    require(build['passed']is True and build['source_sha256']==sha(HERE/'attenuation.cpp'),'Native build source differs')
    require(sha(args.library)==build['library_sha256']==a['library_sha256'],'Native library differs')
    require(sha(args.build_receipt)==a['build_receipt_sha256'],'Native build receipt differs')
    require(a['threads']==2 and a['sampled_process_tree_rss_cap_bytes']==6442450944,'Resource envelope differs')
    return a

def projection(cases,reports):
    # Conservative input-only dimension proxy, not a guaranteed runtime bound.
    dimensions=[v for r in reports for phase in r['plan_dimensions'].values()for v in phase.values()]
    ratio=max(v['space_nodes']/(v['parents']+1)for v in dimensions)
    def work(c):return sum(ratio*(c['parents_'+p]+1)*128*(c['n_'+p]+1)*(c['parents_'+p]+1)for p in('train','test'))
    indexed={c['case_id']:c for c in cases};rate=max(r['wall_seconds']/work(indexed[r['case_id']])for r in reports)
    return dict(method='3*max pilot elapsed/proxy_work applied to full input-only proxy roster; admission heuristic only',
                max_space_nodes_per_parent=ratio,maximum_seconds_per_work=rate,projected_full_seconds=3*rate*sum(work(c)for c in cases),
                work_by_case={c['case_id']:work(c)for c in cases})

def run(args):
    started=time.monotonic();out=Path(args.output).resolve();require(not out.is_relative_to(REPO),'Outputs must be outside the checkout')
    out.mkdir(parents=True,exist_ok=False);result=dict(phase=args.phase,passed=False,cases=[],status='running');write(out/'result.json',result)
    try:
        protocol=read(HERE/'protocol.json');a=admission(args,protocol);cases=verify_inputs(protocol)
        result.update(source_sha256=source_identity(),admission_sha256=sha(args.admission),numerical_attempt_id=a['numerical_attempt_id'],
                      library_sha256=sha(args.library),build_receipt_sha256=sha(args.build_receipt),
                      runtime=runtime_identity(),
                      resources=dict(threads=2,workers=1,sampled_process_tree_rss_cap_bytes=6442450944,memory_scope='Conductor sampled-RSS termination, not an OS-enforced allocation limit'))
        selected=[c for c in cases if c['case_id']in protocol['pilot']];reports=[];prior=0.;resumed=None
        if getattr(args,'resume_training',None) is not None:
            require(args.phase=='pilot','Frozen training resume is only admitted for the original pilot')
            resumed=load_training_resume(args,a,result,out);prior=resumed['prior_seconds']
            result['training_resume']=resumed['provenance']
        else:
            require(not getattr(args,'resume_review',None)and not getattr(args,'resume_archive',None),'Orphan resume arguments')
        if args.phase=='full':
            require(args.pilot is not None,'Full campaign requires reviewed complete pilot');root=Path(args.pilot).resolve();pilot=read(root/'result.json')
            require(a['pilot_result_sha256']==sha(root/'result.json')and a['pilot_output_review_passed']is True,'Full admission does not bind the independently reviewed pilot')
            require(pilot['passed']and pilot['phase']=='pilot'and pilot['source_sha256']==result['source_sha256']and pilot['runtime']['essential']==result['runtime']['essential']and pilot['library_sha256']==result['library_sha256'],'Pilot identity or completion mismatch')
            require([r['case_id']for r in pilot['cases']]==protocol['pilot'],'Pilot fixed roster mismatch')
            for rec in pilot['cases']:
                path=safe(root,rec['file']);require(sha(path)==rec['sha256'],'Pilot case changed');r=read(path);require(r['passed'],'Failed pilot case')
                trace=root/(r['case_id']+'.attempts.jsonl');require(sha(trace)==r['attempts_sha256'],'Pilot attempts changed')
                shutil.copy2(path,out/path.name);shutil.copy2(trace,out/trace.name);reports.append(r)
                result['cases'].append(dict(case_id=r['case_id'],file=path.name,sha256=sha(path),source='exact pilot reuse'))
            if 'training_resume'in pilot:
                provenance=pilot['training_resume']
                for key,relative in provenance['evidence_files'].items():require(sha(safe(root,relative))==provenance[key],'Pilot resume evidence changed')
                shutil.copytree(root/'training_resume',out/'training_resume')
                result['training_resume']=provenance
            prior=pilot.get('cumulative_scientific_seconds',pilot['wall_seconds']);result['pilot_result_sha256']=sha(root/'result.json');result['pilot_runtime']=pilot['runtime']
            estimate=projection(cases,reports);result['projection']=estimate
            require(estimate['projected_full_seconds']<=14400,'Conservative full-campaign admission exceeds wall allowance')
            selected=[c for c in cases if c['case_id']not in protocol['pilot']]
        wall=(1800 if args.phase=='pilot'else 14400)-prior
        require(a['wall_seconds']<=wall and a['wall_seconds']>0,'Phase wall admission exceeds protocol')
        deadline=min(started+a['wall_seconds'],time.monotonic()+(datetime.datetime.fromisoformat(a['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        modules=model.archived();native=model.Native(args.library)
        with threadpool_limits(limits=2):
            result['threadpools']=[{**{k:v for k,v in row.items()if k!='filepath'},'library_sha256':sha(row['filepath'])}for row in threadpool_info()]
            for c in selected:
                require(time.monotonic()<deadline,'Campaign wall cap');result['active_case']=c['case_id'];write(out/'result.json',result)
                reuse=resumed if resumed is not None and c['case_id']==resumed['case_id']else None
                r=case_run(c,modules,native,protocol,out,deadline,reuse);reports.append(r)
                result['cases'].append(dict(case_id=c['case_id'],file=c['case_id']+'.json',sha256=sha(out/(c['case_id']+'.json')),source='exact frozen training reuse; missing test scoring only'if reuse else'new joint fit'))
                write(out/'result.json',result);require(r['passed'],'Case failed; no replacement or zero-outcome conversion')
                print(json.dumps(dict(event='case_complete',case_id=c['case_id'],wall_seconds=r['wall_seconds'])),flush=True)
        require(time.monotonic()<deadline,'Campaign completed after wall cap')
        if args.phase=='full':
            summary=aggregate(reports,protocol);write(out/'summary.json',summary);result['summary_sha256']=sha(out/'summary.json')
            require(sum(len(r['floor_checks'])for r in reports)==480 and sum(len(r['historical_comparisons'])for r in reports)==400,'Historical validation roster mismatch')
        else:result['projection']=projection(cases,reports)
        result.update(passed=True,status='complete',new_fit_count=4*(len(selected)-(1 if resumed else 0)),
                      reused_fit_count=4 if resumed else 4*len(protocol['pilot'])if args.phase=='full'else 0,cumulative_fit_count=4*len(reports),
                      outcome_count=5*len(reports),historical_floor_checks=6*len(reports),historical_comparison_rows=5*len(reports));result.pop('active_case',None)
    except BaseException as exc:result.update(passed=False,status='unknown',error_type=type(exc).__name__,error=str(exc))
    finally:
        result['wall_seconds']=time.monotonic()-started
        result['prior_scientific_seconds']=prior if 'prior'in locals()else 0.
        result['cumulative_scientific_seconds']=result['wall_seconds']+result['prior_scientific_seconds']
        active=result.get('active_case')
        if active and (out/(active+'.json')).exists()and not any(r['case_id']==active for r in result['cases']):
            result['cases'].append(dict(case_id=active,file=active+'.json',sha256=sha(out/(active+'.json')),source='retained partial checkpoint; case did not complete'))
        if active and (out/(active+'.persistence_failure.json')).exists():
            result['persistence_failure']=dict(file=active+'.persistence_failure.json',sha256=sha(out/(active+'.persistence_failure.json')))
        if 'cases'in locals():
            finished={r['case_id']for r in result['cases']}
            result['not_run_case_ids']=[c['case_id']for c in cases if c['case_id']not in finished]
            result['unknown_case_ids']=[r['case_id']for r in result['cases']if not read(out/r['file']).get('passed')]
        write(out/'result.json',result)
    return 0 if result['passed']else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['pilot','full'],required=True)
    for name in('output','library','build-receipt','admission'):p.add_argument('--'+name,required=True)
    p.add_argument('--pilot');p.add_argument('--resume-training');p.add_argument('--resume-review');p.add_argument('--resume-archive');raise SystemExit(run(p.parse_args()))
