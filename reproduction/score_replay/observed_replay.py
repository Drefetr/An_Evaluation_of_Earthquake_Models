"""Held-out observed LI/LI+ scores on exact original quadrature arrays.

CPU BLAS evaluates the original parent contractions without fitting, generating
histories, changing quadrature, or reselecting training winners/gates. At eta=0
the exact OC intensity is evaluated directly. Expected scores enter afterwards.
"""
from __future__ import annotations
import argparse
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, write_new
from reproduction.score_replay.inhibition_replay import grid_digest, KEYS

MODES={'LI':(0,0),'LIplus_immigrant':(1,0),'LIplus_inclusive':(1,1)}


def source_pins():
    base=Path(__file__).parent
    return {name:digest((base/name).read_bytes()) for name in ('__init__.py','core.py','inhibition_replay.py','observed_replay.py')}


def validate_data(data):
    import numpy as np
    for key,width in [('parents',6),('events',6),('space',5)]:
        a=data[key]
        if a.ndim!=2 or a.shape[1]!=width or a.dtype!=np.dtype('float64') or not np.isfinite(a).all():raise ValueError('prepared shape/type/finite '+key)
    for key in ('times','weights','meta'):
        if data[key].ndim!=1 or data[key].dtype!=np.dtype('float64') or not np.isfinite(data[key]).all():raise ValueError('prepared vector '+key)
    if len(data['meta'])!=9 or len(data['times'])!=len(data['weights']) or not len(data['space']) or not len(data['times']):raise ValueError('prepared vector sizes')
    p,e,s,t,w,m=(data[k] for k in KEYS)
    if np.any(np.diff(p[:,0])<0) or np.any(np.diff(t)<=0) or np.any(w<=0) or np.any(p[:,3:5]<0) or np.any(p[:,5]<=0) or np.any(e[:,3:]<0) or np.any(s[:,2:]<0):raise ValueError('prepared chronology/nonnegative domain')
    a,d,n,c,power,T,base,marks,sigma=m
    if not (-12<=a<=0 and -2<=d<=2 and 0<=n<=.98 and .0001<=c<=20 and 1.01<=power<=2.5 and T>0 and sigma>0 and base>=0):raise ValueError('prepared backbone outside original bounds')


def score(data, parameters, plus, inclusive, chunk_bytes):
    """Return score components only; no expected values or gradient claims."""
    import numpy as np
    validate_data(data)
    eta,logell,logpsi=map(float,parameters)
    if not (0<=eta<=4 and math.log(5)<=logell<=math.log(150) and math.log(1/24)<=logpsi<=math.log(365)) or plus not in (0,1) or inclusive not in (0,1):raise ValueError('original inhibition parameter bounds')
    parents,events,space,times,weights,meta=(data[k] for k in KEYS)
    a,d,n,c,power,T,base,marks,sigma=map(float,meta)
    ell,psi=math.exp(logell),math.exp(logpsi);gamma=.75*math.log(10) if plus else 0.
    logB=np.full(len(events),-np.inf);positive=events[:,3]>0
    logB[positive]=a+d*(2*events[positive,0]/T-1)+np.log(events[positive,3])
    logH=np.full(len(events),-np.inf);positive=events[:,4]>0;logH[positive]=np.log(events[positive,4])
    point_terms=np.logaddexp(logB,logH)
    if eta:
        for index,event in enumerate(events):
            lag=event[0]-parents[:,0];past=lag>0
            r2=(event[1]-parents[past,1])**2+(event[2]-parents[past,2])**2
            stress=math.fsum((np.exp(gamma*parents[past,3]-lag[past]/psi)/(1+r2/(ell*ell))**2).tolist())
            point_terms[index]=point_terms[index]-eta*stress if inclusive else np.logaddexp(logB[index]-eta*stress,logH[index])
    point=math.fsum(point_terms.tolist());deficit=0.;tiles=0;tile_rows=0
    if eta:
        # Temporal contractions have exact strict-past support. Negative lags
        # are clamped before exponentiation only to avoid computing unused
        # overflow values; their matrix entries are then exactly zero.
        lag=times[None,:]-parents[:,0,None];past=lag>0;lag=np.maximum(lag,0.)
        temporal=(power-1)/c*np.exp(-power*np.log1p(lag/c));temporal[~past]=0.
        decay=np.exp(-lag/psi);decay[~past]=0.;del lag,past
        magnitude=np.exp(gamma*parents[:,3])
        if not np.isfinite(magnitude).all():raise ArithmeticError('nonfinite stress mark')
        background_time=np.exp(a+d*(2*times/T-1))
        # Conservative live-array allowance: spatial/radial intermediates and
        # H,G,attenuation/weight matrices. Temporal arrays are separate shared
        # allocations reported below; the external supervisor caps total RSS.
        per_space=8*(8*len(parents)+8*len(times)+16)
        tile_rows=min(len(space),max(1,int(chunk_bytes//max(1,per_space))))
        if per_space>chunk_bytes:raise MemoryError('one spatial tile exceeds declared scratch budget')
        totals=[]
        for begin in range(0,len(space),tile_rows):
            nodes=space[begin:begin+tile_rows]
            r2=(nodes[:,0,None]-parents[None,:,1])**2+(nodes[:,1,None]-parents[None,:,2])**2
            radial=magnitude[None,:]/(1+r2/(ell*ell))**2
            stress=radial@decay
            attenuation=nodes[:,3,None]*background_time[None,:]
            if inclusive:
                coeff=np.exp(-2*np.log1p(r2/(sigma*sigma)))
                coeff*=parents[None,:,4]/parents[None,:,5]
                coeff*=nodes[:,4,None]
                attenuation+=n*(coeff@temporal)
            decrement=-np.expm1(-eta*stress)
            decrement*=attenuation
            decrement*=weights[None,:]
            decrement*=nodes[:,2,None]
            totals.append(float(np.sum(decrement,dtype=np.float64)));tiles+=1
        deficit=math.fsum(totals)
        shared_bytes=temporal.nbytes+decay.nbytes
    else:
        shared_bytes=0
    exposure=base-deficit;joint=point-exposure+marks
    if not all(math.isfinite(v) for v in (point,deficit,exposure,joint)) or exposure < -1e-7:raise ArithmeticError('nonfinite/negative score components')
    return dict(parameters=list(parameters),P=point,E=exposure,C=-exposure,M=marks,joint=joint,nll=-joint,deficit=deficit,timing=None,location=None,n_events=len(events),tiles=tiles,tile_rows=tile_rows,shared_temporal_bytes=shared_bytes,eta_zero_exact_branch=eta==0,gradient_scope='Not evaluated: score-only replay',split_scope='Original joint point-intensity functional; no separately evaluated ground timing/location split')


def tiny_controls():
    """Invented data; compare BLAS and tiled output to direct scalar sums."""
    import numpy as np
    data=dict(parents=np.array([[.2,0.,0.,.1,1.,1.],[.7,.5,-.2,.3,.8,1.2]]),events=np.array([[.2,.2,.1,.1,.03,.1],[1.,.2,.1,.1,.03,.1]]),space=np.array([[0.,0.,.5,.1,.1],[1.,1.,.5,.1,.1]]),times=np.array([.5,1.5]),weights=np.array([1.,1.]),meta=np.array([-2.,.1,.3,.05,1.3,2.,.8,-.2,10.]))
    records=[];a,d,n,c,power,T,base,marks,sigma=map(float,data['meta'])
    for name,(plus,inclusive) in MODES.items():
        for eta in (0.,.4):
            pars=[eta,math.log(10),math.log(2)];gamma=.75*math.log(10) if plus else 0.;deficit=0.;point=0.
            for s in data['space']:
                for t,w in zip(data['times'],data['weights']):
                    G=0.;H=0.
                    for parent in data['parents']:
                        lag=t-parent[0]
                        if lag<=0:continue
                        r2=(s[0]-parent[1])**2+(s[1]-parent[2])**2
                        G+=math.exp(gamma*parent[3]-lag/2)/(1+r2/100)**2
                        H+=parent[4]*math.exp(-2*math.log1p(r2/(sigma*sigma)))*s[4]/parent[5]*(power-1)/c*math.exp(-power*math.log1p(lag/c))
                    B=math.exp(a+d*(2*t/T-1))*s[3]
                    deficit+=w*s[2]*(B+(n*H if inclusive else 0))*(-math.expm1(-eta*G))
            for event in data['events']:
                G=0.
                for parent in data['parents']:
                    lag=event[0]-parent[0]
                    if lag>0:G+=math.exp(gamma*parent[3]-lag/2)/(1+((event[1]-parent[1])**2+(event[2]-parent[2])**2)/100)**2
                B=math.exp(a+d*(2*event[0]/T-1))*event[3]
                point+=math.log(B+event[4])-eta*G if inclusive else math.log(B*math.exp(-eta*G)+event[4])
            one=score(data,pars,plus,inclusive,384);full=score(data,pars,plus,inclusive,1024*1024)
            delta=max(abs(one['P']-point),abs(one['deficit']-deficit),abs(one['nll']-(base-deficit-point-marks)),abs(one['nll']-full['nll']))
            records.append(dict(model=name,eta=eta,max_absolute_delta=float(delta),passed=bool(delta<=1e-12)))
    return dict(passed=all(r['passed'] for r in records),rows=records,scope='Hand-authored direct scalar contractions, strict-past tie, all three modes, zero/positive eta and forced split/full tile equivalence; no historical score calls.')


def load_data(inputs,row):
    import numpy as np
    raw=inputs.read(row['prepared'])
    with np.load(io.BytesIO(raw),allow_pickle=False) as stream:data={k:np.ascontiguousarray(stream[k]) for k in KEYS}
    if grid_digest(data)!=row['input_digest'] or [len(data[k]) for k in KEYS[:4]]!=row['counts']:raise ValueError('original prepared array identity mismatch')
    validate_data(data);return data


def check_fresh_floor(fresh, source, actual, row):
    entry=fresh['rows'][row['fresh_score_row_id']];path=Path(entry['result_path']);raw=path.read_bytes()
    if digest(raw)!=entry['sha256']:raise ValueError('fresh OC result SHA mismatch')
    report=json.loads(raw)
    if report.get('passed') is not True or report.get('status')!='replayed' or report.get('id')!=row['fresh_score_row_id']:raise ValueError('fresh OC identity/status')
    for key,value in row['fresh_source_identity'].items():
        if report['actual'].get(key)!=value:raise ValueError('fresh OC '+key+' mismatch')
    if report['actual']['parameters']!=source['backbone_parameters']:raise ValueError('fresh OC backbone vector mismatch')
    reference=report['actual']['components'];checks=[]
    for key in ('P','E','M','joint','n_events'):
        delta=abs(actual[key]-reference[key]);tol=0 if key=='n_events' else 1e-6
        checks.append(dict(field=key,delta=delta,absolute_tolerance=tol,passed=delta<=tol))
    if not all(c['passed'] for c in checks):raise ValueError('prepared floor disagrees with fresh OC score')
    return dict(result_sha256=digest(raw),id=report['id'],checks=checks)


def run(registry_path,admission_path,fresh_path,output,selected,mode):
    if output.exists():raise FileExistsError(output)
    rb=registry_path.read_bytes();registry=json.loads(rb);ib=(registry_path.parent/'input_manifest.json').read_bytes();ab=admission_path.read_bytes();admission=json.loads(ab);fb=fresh_path.read_bytes();fresh=json.loads(fb)
    rows={r['id']:r for r in registry['rows']};selected=selected or list(rows)
    if len(rows)!=len(registry['rows']) or len(set(selected))!=len(selected) or not selected or set(selected)-set(rows):raise ValueError('invalid fixed roster')
    for key,value in [('passed',True),('mode',mode),('registry_sha256',digest(rb)),('input_manifest_sha256',digest(ib)),('source_sha256',source_pins()),('fresh_scores_sha256',digest(fb)),('row_ids',selected)]:
        if admission.get(key)!=value:raise ValueError('admission mismatch '+key)
    threads=admission.get('numeric_threads');budget=admission.get('chunk_bytes')
    if type(threads)!=int or threads not in (1,2) or type(budget)!=int or not 64*2**20<=budget<=512*2**20:raise ValueError('invalid fixed thread/scratch cap')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]=str(threads)
    import numpy as np
    from threadpoolctl import threadpool_info,threadpool_limits
    inputs=Inputs(registry_path.parent);output.mkdir(parents=True);began=time.monotonic();reports=[]
    with threadpool_limits(limits=threads):
        if any(x['num_threads']>threads for x in threadpool_info()):raise RuntimeError('thread cap')
        pools=threadpool_info()
        backend_pins={str(v['filepath']):digest(Path(v['filepath']).read_bytes()) for v in pools if v.get('filepath')}
        write_new(output/'launch.json',dict(registry_sha256=digest(rb),input_manifest_sha256=digest(ib),source_sha256=source_pins(),admission_sha256=digest(ab),fresh_scores_sha256=digest(fb),mode=mode,row_ids=selected,runtime=dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),threadpools=pools,numerical_backend_sha256=backend_pins,numeric_threads=threads,scratch_bytes=budget)))
        controls=tiny_controls();write_new(output/'controls.json',controls)
        if not controls['passed']:raise ArithmeticError('tiny scalar/BLAS controls failed')
        for index,rowid in enumerate(selected):
            row=rows[rowid];folder=output/'rows'/f'{index:05d}';tick=time.monotonic();report=dict(id=rowid,passed=False,status='failed')
            try:
                data=load_data(inputs,row);source=inputs.json(row['selected_states']);actual={}
                for model,(plus,inclusive) in MODES.items():
                    actual[model]={}
                    for label in ('selected','floor'):
                        actual[model][label]=score(data,source['models'][model][label],plus,inclusive,budget)
                        write_new(folder/'components'/(model+'_'+label+'.json'),dict(model=model,state=label,actual=actual[model][label],prepared_sha256=row['prepared']['sha256'],state_sha256=row['selected_states']['sha256']))
                floor=actual['LI']['floor'];dependency=check_fresh_floor(fresh,source,floor,row)
                # All requested likelihood values have been evaluated before
                # opening the separate historical score reference resource.
                expected=inputs.json(row['expected']);checks=[];comparisons=[]
                for model in MODES:
                    for label in ('selected','floor'):
                        for key in ('nll','P','deficit'):
                            value=actual[model][label][key];ref=expected['models'][model][label][key];delta=value-ref
                            tol=registry['absolute_tolerance'] if label=='selected' else registry['floor_tolerance']
                            checks.append(dict(model=model,state=label,field=key,actual=value,expected=ref,delta=delta,absolute_tolerance=tol,passed=abs(delta)<=tol))
                for choice in source['procedures']:
                    model=choice['model'];label=choice['state'];value=actual[model][label];gain=floor['nll']-value['nll'];reference=next(v for v in expected['comparisons'] if (v['model'],v['gate'])==(model,choice['gate']));delta=gain-reference['gain']
                    comparisons.append(dict(model=model,gate=choice['gate'],gain=gain,original_gain=reference['gain'],delta=delta,absolute_tolerance=registry['absolute_tolerance'],win=gain>0,off_floor=value['parameters'][0]>0,selected_state=label,selected_state_index=choice['selected_state_index'],passed=abs(delta)<=registry['absolute_tolerance'] and (gain>0)==reference['win'] and (value['parameters'][0]>0)==reference['off_floor']))
                passed=all(c['passed'] for c in checks+comparisons)
                report.update(passed=passed,status='replayed' if passed else 'failed',actual=actual,comparison=dict(passed=passed,checks=checks,comparisons=comparisons),prepared_sha256=row['prepared']['sha256'],input_digest=row['input_digest'],state_sha256=row['selected_states']['sha256'],source_state_sha256=source['original_state_sha256'],original_fit_sha256=source['original_fit_sha256'],fresh_floor=dependency,feature_scope='Exact original prepared arrays and unchanged quadrature; CPU BLAS contractions',selection_scope='Original saved winners and gate choices retained; no training likelihood or optimizer/gate reselection in this held-out replay.')
                del data
            except Exception as exc:report.update(error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
            report['component_records']={p.stem:dict(path=p.relative_to(output).as_posix(),sha256=digest(p.read_bytes())) for p in sorted((folder/'components').glob('*.json'))}
            report['elapsed_seconds']=time.monotonic()-tick;path=folder/'result.json';write_new(path,report)
            entry=dict(id=rowid,passed=report['passed'],status=report['status'],result=path.relative_to(output).as_posix(),sha256=digest(path.read_bytes()),elapsed_seconds=report['elapsed_seconds']);reports.append(entry)
            with (output/'progress.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(entry)+'\n');stream.flush()
        if any(x['num_threads']>threads for x in threadpool_info()):raise RuntimeError('final thread cap')
    result=dict(schema='observed_s04_saved_state_replay_v1',passed=all(r['passed'] for r in reports),mode=mode,full_registry=selected==list(rows),registry_sha256=digest(rb),requested_rows=len(selected),completed_rows=len(reports),passed_rows=sum(r['passed'] for r in reports),failed_rows=sum(not r['passed'] for r in reports),rows=reports,elapsed_seconds=time.monotonic()-began,controls_sha256=digest((output/'controls.json').read_bytes()),scope='Held-out original quadrature orders at exact saved selected/floor states; recorded training gate choices, no fitting/generation/reselection.',entire_task_complete=False)
    write_new(output/'result.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('registry','admission','fresh-scores','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--rows',type=Path);parser.add_argument('--mode',choices=('pilot','full','completion'),required=True)
    args=parser.parse_args();result=run(args.registry.resolve(),args.admission.resolve(),args.fresh_scores.resolve(),args.output.resolve(),json.loads(args.rows.read_bytes()) if args.rows else None,args.mode)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}));raise SystemExit(0 if result['passed'] else 1)
