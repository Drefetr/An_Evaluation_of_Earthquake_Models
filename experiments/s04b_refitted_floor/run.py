"""Train-only scalar-background sensitivity on the exact saved S04B histories.

This module never calls the archived generator, inhibitor fitter or area/time
quadrature. Actual cases require an independently reviewed numerical admission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_name] = '1'

import numpy as np
import scipy
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INPUT = REPO / 'reproduction/synthetic'
MODELS = ('LI', 'LIplus_immigrant', 'LIplus_inclusive')
PILOT_SEEDS = (410401, 410501, 410601, 410701)
A_BOUNDS = (-12.0, 0.0)
FLOOR_TOL = 1e-4
COMPONENT_TOL = 1e-9
FROZEN_PROTOCOL_SHA256 = 'a1794b96655812cc83291f56f6f3fe58a51baca98d96aa2de089ebcc8c9d7a29'


def read(path):
    def reject_nonfinite(value):
        raise ValueError('Nonfinite JSON constant: '+value)
    return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=reject_nonfinite)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(temporary, path)


def close(actual, expected, tolerance, label):
    if not math.isfinite(actual) or not math.isfinite(expected) or abs(actual - expected) > tolerance:
        raise ArithmeticError(f'{label}: {actual!r}, expected {expected!r}, tolerance {tolerance}')


def safe_input(relative, root=INPUT):
    candidate = Path(relative)
    path = (root / candidate).resolve()
    if candidate.is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError('Input path escapes the frozen bundle')
    return path


def integral(d, start, end, T0):
    if not all(math.isfinite(v) for v in (d, start, end, T0)) or not end > start or T0 <= 0:
        raise ValueError('Invalid time integral inputs')
    z = d * (end - start) / T0
    sinc_h = 1 + z*z/6 + z**4/120 if abs(z) < 1e-5 else math.sinh(z)/z
    return (end-start) * math.exp(d*((start+end)/T0-1)) * sinc_h


def sufficient(features, d, n):
    """Precompute a fixed baseline once; no optimization or spatial calls here."""
    bspace = np.asarray(features['b'], dtype=float)
    x = np.asarray(features['x'], dtype=float)
    hp = np.asarray(features['hp'], dtype=float)
    hg = np.asarray(features['hg'], dtype=float)
    if any(a.ndim != 1 for a in (bspace, x, hp, hg)) or len({len(a) for a in (bspace, x, hp, hg)}) != 1:
        raise ValueError('Feature vector shape mismatch')
    if not all(np.isfinite(a).all() for a in (bspace, x, hp, hg)):
        raise ValueError('Nonfinite feature vector')
    if np.any(bspace <= 0) or np.any(hp < 0) or np.any(hg < 0) or not math.isfinite(n) or n < 0:
        raise ValueError('Invalid nonnegative baseline features')
    A = integral(d, features['start'], features['end'], features['T0'])
    h = n * float(features['exposure'])
    M = float(features['marks'])
    if not all(math.isfinite(v) for v in (A, h, M)) or A <= 0 or h < 0:
        raise ValueError('Invalid exposure or marks')
    g = np.exp(d*x)
    result = dict(u=g*bspace, v=n*hp, ground_u=g, ground_v=n*hg,
                  A=A, H=h, M=M, N=len(x))
    if not all(np.isfinite(result[k]).all() for k in ('u', 'v', 'ground_u', 'ground_v')):
        raise ValueError('Nonfinite sufficient statistics')
    return result


def components(s, b):
    if not math.isfinite(b) or b <= 0:
        raise ValueError('The background rate must be positive and finite')
    point = b*s['u'] + s['v']
    ground = b*s['ground_u'] + s['ground_v']
    if np.any(point <= 0) or np.any(ground <= 0) or not np.isfinite(point).all() or not np.isfinite(ground).all():
        raise ArithmeticError('Invalid baseline intensity')
    P = float(np.log(point).sum())
    G = float(np.log(ground).sum())
    E = b*s['A'] + s['H']
    M = s['M']
    result = dict(P=P, E=E, C=-E, M=M, joint=P-E+M, nll=E-P-M,
                  timing=G-E, location=P-G, background_exposure=b*s['A'],
                  triggering_exposure=s['H'])
    if not all(math.isfinite(v) for v in result.values()):
        raise ArithmeticError('Nonfinite score component')
    return result


def derivative(s, b):
    value = float(np.sum(s['u']/(b*s['u']+s['v'])) - s['A'])
    if not math.isfinite(value):
        raise ArithmeticError('Nonfinite scalar derivative')
    return value


def fit_intercept(s, historical_a):
    """The unique bounded concave-rate optimum, including endpoint cases."""
    if not math.isfinite(historical_a) or not A_BOUNDS[0] <= historical_a <= A_BOUNDS[1]:
        raise ValueError('Historical intercept outside the declared box')
    lower, upper = map(math.exp, A_BOUNDS)
    dl, du = derivative(s, lower), derivative(s, upper)
    if dl < du:
        raise ArithmeticError('Concavity derivative order failed')
    iterations = 0
    if dl <= 0:
        b, selected = lower, 'lower'
    elif du >= 0:
        b, selected = upper, 'upper'
    else:
        b, info = brentq(lambda value: derivative(s, value), lower, upper,
                         xtol=1e-14, rtol=1e-12, maxiter=200, full_output=True, disp=True)
        if not info.converged:
            raise ArithmeticError('Scalar root did not converge')
        iterations, selected = info.iterations, 'interior'
    residual = derivative(s, b)
    scale = max(1., s['A'], float(np.sum(s['u']/(b*s['u']+s['v']))))
    if selected == 'interior' and abs(residual)/scale > 1e-9:
        raise ArithmeticError('Interior derivative residual exceeds the frozen tolerance')
    if selected == 'lower' and residual > 0 or selected == 'upper' and residual < 0:
        raise ArithmeticError('Endpoint KKT sign failed')
    score = components(s, b)
    historical = components(s, math.exp(historical_a))
    if score['joint'] < historical['joint'] - 1e-9:
        raise ArithmeticError('Train fit worsens the included historical intercept')
    return dict(a=math.log(b), b=b, selection=selected, bounds_a=list(A_BOUNDS),
                initial_bracket_b=[lower, upper], endpoint_derivatives=[dl, du],
                derivative=residual, relative_derivative=abs(residual)/scale,
                root_iterations=int(iterations), historical_a=historical_a,
                historical_b=math.exp(historical_a), train_joint_gain=score['joint']-historical['joint'])


def validate_roster(cases):
    if len(cases) != 80 or len({c['case_id'] for c in cases}) != 80:
        raise ValueError('Exactly 80 unique cases required')
    for regime in range(4, 8):
        seeds = sorted(c['seed'] for c in cases if c['regime'] == regime)
        if seeds != list(range(410001+100*regime, 410021+100*regime)):
            raise ValueError('Frozen regime seed roster mismatch')


def verify_inputs():
    if sha(HERE/'protocol.json') != FROZEN_PROTOCOL_SHA256:
        raise ValueError('The independently reviewed protocol changed')
    pins = read(HERE/'source_pins.json')
    for relative, expected in pins.items():
        path = safe_input(relative, REPO)
        if sha(path) != expected:
            raise ValueError('Frozen scientific source changed: '+relative)
    manifest = read(INPUT/'input_manifest.json')
    entries = {row['path']: row for row in manifest['files']}
    if len(entries) != len(manifest['files']):
        raise ValueError('Duplicate manifest file')
    cases = manifest['s04b']['cases']
    validate_roster(cases)
    checked, workload = {}, {}
    for case in cases:
        paths = [case[k] for k in ('history', 'generator_receipt', 'states', 'expected')] + list(case['fits'].values())
        if set(case['fits']) != set(MODELS):
            raise ValueError('Missing original model fit')
        for relative in paths:
            path = safe_input(relative)
            record = entries[relative]
            actual = sha(path)
            if path.stat().st_size != record['bytes'] or actual != record['sha256']:
                raise ValueError('Changed exact input: '+relative)
            checked[relative] = actual
        with np.load(safe_input(case['history']), allow_pickle=False) as loaded:
            rows = loaded['rows'].copy()
        if rows.ndim != 2 or rows.shape[1] != 4 or not np.isfinite(rows).all() or np.any(np.diff(rows[:,0]) < 0):
            raise ValueError('Invalid history shape, chronology or finiteness')
        if hashlib.sha256(rows.tobytes()).hexdigest() != case['rows_sha256']:
            raise ValueError('Decompressed history hash changed')
        if np.any(rows[:,0] < 0) or np.any(rows[:,0] >= 760) or np.any(rows[:,3] < 0):
            raise ValueError('History outside declared interval or marks')
        for phase, start, end in [('train',30,395), ('test',395,760)]:
            if int(np.sum((rows[:,0] >= start) & (rows[:,0] < end))) != case['n_'+phase]:
                raise ValueError('Frozen phase count changed')
        workload[case['case_id']] = int((case['n_train']+case['n_test'])*len(rows)+len(rows)*9+2*9)
    return cases, checked, workload


def load_archive():
    spec = importlib.util.spec_from_file_location('_refitted_floor_archived_replay', INPUT/'replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    return replay, replay.scientific_modules()


def verified_radial(library, receipt):
    library, receipt = Path(library).resolve(), Path(receipt).resolve()
    build = read(receipt)
    pinned = read(HERE/'source_pins.json')['reproduction/synthetic/source/radial.cpp']
    if build['sources']['radial.cpp'] != pinned:
        raise ValueError('Radial build source mismatch')
    if build['libraries']['radial']['sha256'] != sha(library):
        raise ValueError('Radial library differs from build receipt')
    if build['libraries']['radial']['file'] != library.name:
        raise ValueError('Radial library name mismatch')
    return dict(library_sha256=sha(library), build_receipt_sha256=sha(receipt), radial_source_sha256=pinned)


def crosscheck(c, features, s, a, d, n):
    expected = c.S.evaluate(features, [a,d,n])[0]
    actual = components(s, math.exp(a))
    aliases = {'P':'point','E':'compensator','M':'mark','joint':'joint','nll':'nll','timing':'timing','location':'location'}
    deltas = {}
    for new, old in aliases.items():
        close(actual[new], expected[old], COMPONENT_TOL, 'Archived formula '+new)
        deltas[new] = actual[new] - expected[old]
    return deltas


def saved_floor(expected, states, fits, model, phase):
    index = next(i for i,row in enumerate(states[model]) if row['pars'] == fits[model]['floor'])
    order = 16 if phase == 'train' else 32
    return expected['phase_values'][f'order{order}_{phase}'][model][index]


def score_case(case, c, replay, geometry, deadline, report_path=None):
    import psutil
    started = time.monotonic()
    with np.load(safe_input(case['history']), allow_pickle=False) as loaded:
        rows = loaded['rows'].copy()
    fits = {name:read(safe_input(path)) for name,path in case['fits'].items()}
    for fit in fits.values():
        replay.saved_selection(fit)
    states, expected = read(safe_input(case['states'])), read(safe_input(case['expected']))
    name = c.G.MATCHED_NAMES[case['regime']-4]
    _, background, eta, ell, psi = c.G.ROSTER[name]
    law = c.G.Law(name,case['seed'],background,eta,ell,psi)
    gm = c.G.fitting_metadata(law)
    pars = [law.a,law.d,law.n,math.log(law.c),law.p]
    result = dict(case_id=case['case_id'], regime=case['regime'], seed=case['seed'], passed=False,
                  fixed_backbone=dict(a_historical=law.a,d=law.d,n=law.n,c=law.c,p=law.p,beta=law.beta,sigma=law.sigma,r=law.r,T0=law.T0),
                  fixed_spatial_configuration=gm,
                  input_identity={k:case[k] for k in ('history','rows_sha256','states','fits','expected')},
                  phases={}, historical_floor_checks=[])
    if report_path:
        write(report_path,result)
    peak_sample = psutil.Process().memory_info().rss
    for phase,start,end in [('train',30,395),('test',395,760)]:
        if time.monotonic() >= deadline:
            raise TimeoutError('Frozen campaign wall cap exceeded')
        meta = dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
        arrays = c.canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),
                                   np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),
                                   np.asarray(gm['kde_weight']),meta,pars,geometry)
        features = c.S.features(arrays,meta,pars[3:5])
        s = sufficient(features,law.d,law.n)
        if s['N'] != case['n_'+phase]:
            raise ValueError('Constructed phase target count mismatch')
        old = components(s,math.exp(law.a))
        control_old = crosscheck(c,features,s,law.a,law.d,law.n)
        for model in MODELS:
            value = saved_floor(expected,states,fits,model,phase)
            close(old['nll'],float(value[0]),FLOOR_TOL,'Saved historical '+phase+'/'+model)
            result['historical_floor_checks'].append(dict(phase=phase,model=model,actual_nll=old['nll'],saved_nll=value[0],delta=old['nll']-value[0]))
        if phase == 'train':
            result['fit'] = fit_intercept(s,law.a)
        # The train fit is complete and frozen before any test feature scoring.
        chosen = result['fit']
        new = components(s,chosen['b'])
        control_new = crosscheck(c,features,s,chosen['a'],law.d,law.n)
        v = saved_floor(expected,states,fits,'LI',phase)
        historical = dict(old)
        historical.update(P=float(v[5]), E=float(v[0]+v[5]+s['M']), C=-float(v[0]+v[5]+s['M']),
                          joint=-float(v[0]), nll=float(v[0]))
        ground_point = old['timing'] + old['E']
        historical.update(timing=ground_point-historical['E'],
                          location=historical['P']-ground_point,
                          triggering_exposure=historical['E']-historical['background_exposure'])
        # The archived point sum + observed mark reconstructs its signed exposure.
        close(historical['P']+historical['C']+historical['M'],historical['joint'],COMPONENT_TOL,'Saved component identity')
        for key in ('P','E','joint'):
            close(historical[key],old[key],FLOOR_TOL,'Saved component reconstruction '+key)
        delta = {key:new[key]-historical[key] for key in ('P','E','C','M','joint')}
        close(delta['joint'],delta['P']+delta['C']+delta['M'],COMPONENT_TOL,'Signed component delta')
        if delta['M'] != 0 or delta['C'] != -delta['E']:
            raise ArithmeticError('Mark or signed exposure identity changed')
        result['phases'][phase] = dict(n_events=s['N'],n_parents=len(arrays['parent_time']),
                                      historical=historical,refitted=new,delta=delta,
                                      formula_crosschecks=dict(historical=control_old,refitted=control_new))
        if report_path:
            write(report_path,result)
        peak_sample = max(peak_sample,psutil.Process().memory_info().rss)
        del arrays,features,s
    if len(result['historical_floor_checks']) != 6:
        raise ValueError('Six historical floor comparisons required per case')
    outcomes=[]
    for model in MODELS:
        f = fits[model]
        active = f['floor_nll']-f['selected']['nll'] > 1.5*math.log(max(case['n_train'],1))
        for gate in (('raw',) if model == 'LI' else ('raw','BIC')):
            chosen = f['selected']['pars'] if gate == 'raw' or active else f['floor']
            original = next(row for row in expected['results'] if (row['model'],row['gate']) == (model,gate))
            index = original['selected_state_index']
            if states[model][index]['pars'] != chosen or original['off_floor'] != (chosen[0] > 0):
                raise ValueError('Original gate/selected-state identity mismatch')
            values = expected['phase_values']['order32_test'][model][index]
            floor = saved_floor(expected,states,fits,model,'test')
            close(floor[0]-values[0],original['gain'],COMPONENT_TOL,'Saved gain identity')
            old_floor = -float(floor[0]); procedure = -float(values[0])
            delta_floor = result['phases']['test']['refitted']['joint']-old_floor
            new_gain = procedure-result['phases']['test']['refitted']['joint']
            close(new_gain,original['gain']-delta_floor,COMPONENT_TOL,'Refitted gain identity')
            outcomes.append(dict(model=model,gate=gate,original_training_threshold_exceeded=active,
                                 original_off_floor=original['off_floor'],selected_state_index=index,
                                 original_gain=original['gain'],saved_procedure_test_joint=procedure,
                                 original_floor_test_joint=old_floor,refitted_floor_delta_joint=delta_floor,
                                 new_gain=new_gain,new_win=new_gain>0))
    result.update(outcomes=outcomes,passed=True,wall_seconds=time.monotonic()-started,
                  sampled_self_peak_rss_bytes=peak_sample,
                  memory_scope='Samples at phase boundaries; external supervisor owns process-tree enforcement.')
    return result


def aggregate(reports):
    validate_roster(reports)
    if any(not r.get('passed') or len(r.get('historical_floor_checks',[])) != 6 for r in reports):
        raise ValueError('Incomplete or failed full roster')
    output=[]
    for regime in range(4,8):
        group=[r for r in reports if r['regime']==regime]
        for model in MODELS:
            for gate in (('raw',) if model=='LI' else ('raw','BIC')):
                rows=[next(v for v in r['outcomes'] if (v['model'],v['gate'])==(model,gate)) for r in group]
                output.append(dict(regime=regime,model=model,gate=gate,N=len(rows),
                                   original_mean_gain=math.fsum(v['original_gain'] for v in rows)/len(rows),
                                   refitted_floor_mean_delta_joint=math.fsum(v['refitted_floor_delta_joint'] for v in rows)/len(rows),
                                   mean_gain=math.fsum(v['new_gain'] for v in rows)/len(rows),
                                   wins=sum(v['new_win'] for v in rows)))
    return output


def run(args):
    started=time.monotonic(); output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    report=dict(schema='s04b_refitted_floor_run_v1',phase=args.phase,passed=False,reports=[],scientific_scope=read(HERE/'protocol.json')['scope'])
    write(output/'result.json',report)
    try:
        if args.acknowledge_reviewed_numerical_admission != 'TRAIN_ONLY_FIXED_ROSTER':
            raise ValueError('Actual scoring requires the reviewed numerical admission acknowledgement')
        cases,pins,workload=verify_inputs()
        native=verified_radial(args.radial,args.build_receipt)
        identity=dict(sources={p.name:sha(p) for p in (HERE/'run.py',HERE/'protocol.json',HERE/'source_pins.json')},
                      input_manifest_sha256=sha(INPUT/'input_manifest.json'),native=native)
        report.update(identity=identity,inputs=pins,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,workload=workload)
        write(output/'result.json',report)
        selected=[c for c in cases if c['seed'] in PILOT_SEEDS] if args.phase=='pilot' else cases
        report_paths=[]; completed=[]
        pilot_seconds=0.
        if args.phase=='full':
            if not args.pilot:
                raise ValueError('Full run requires the exact completed pilot')
            pilotdir=Path(args.pilot).resolve(); prior=read(pilotdir/'result.json')
            if not prior.get('passed') or prior['phase']!='pilot' or prior['identity']!=identity:
                raise ValueError('Pilot did not pass under these exact source/input/native identities')
            for record in prior['reports']:
                path=safe_input(record['file'],pilotdir)
                if sha(path)!=record['sha256']:
                    raise ValueError('Pilot case report changed')
                value=read(path)
                if not value['passed']:
                    raise ValueError('Failed pilot case')
                original_case=next((c for c in cases if c['case_id']==value['case_id']),None)
                if original_case is None or (value['seed'],value['regime'])!=(original_case['seed'],original_case['regime']):
                    raise ValueError('Pilot case identity differs from frozen roster')
                if record['file']!=value['case_id']+'.json' or len(value['historical_floor_checks'])!=6:
                    raise ValueError('Pilot path or historical comparison count differs')
                completed.append(value)
            if sorted(r['seed'] for r in completed)!=list(PILOT_SEEDS):
                raise ValueError('Exact four-case pilot required')
            pilot_seconds=prior['wall_seconds']
            remaining=[c for c in cases if c['seed'] not in PILOT_SEEDS]
            rate=max(r['wall_seconds']/workload[r['case_id']] for r in completed)
            setup_allowance=float(prior['setup_wall_seconds'])
            projected=3*rate*sum(workload[c['case_id']] for c in remaining)+setup_allowance
            report['resource_admission']=dict(pilot_wall_seconds=pilot_seconds,
                                              observed_setup_allowance_seconds=setup_allowance,
                                              remaining_projection_seconds=projected,
                                              total_projection_seconds=projected+pilot_seconds,
                                              formula='pilot_wall + 3*max(pilot_case_time/W)*sum(remaining W) + observed_pilot_setup')
            if not math.isfinite(projected+pilot_seconds) or min(pilot_seconds,setup_allowance,rate)<0 or projected+pilot_seconds>7200:
                raise TimeoutError('Conservative pilot projection exceeds campaign total cap')
            selected=remaining
            for value in completed:
                file=value['case_id']+'.json';write(output/file,value)
                report_paths.append(dict(file=file,sha256=sha(output/file),source='exact pilot reuse'))
        cap=600 if args.phase=='pilot' else 7200-pilot_seconds
        deadline=started+cap
        replay,c=load_archive(); geometry=c.S.Geometry(args.radial)
        report['setup_wall_seconds']=time.monotonic()-started
        for case in selected:
            if time.monotonic()>=deadline:
                raise TimeoutError('Campaign cap reached before next fixed case')
            file=case['case_id']+'.json'
            report['active_case']=case['case_id']
            write(output/'result.json',report)
            write(output/file,dict(case_id=case['case_id'],passed=False,status='started'))
            try:
                value=score_case(case,c,replay,geometry,deadline,output/file)
            except Exception as exc:
                partial=read(output/file)
                partial.update(passed=False,error_type=type(exc).__name__,error=str(exc))
                write(output/file,partial)
                report['failed_case']=dict(file=file,sha256=sha(output/file))
                raise
            completed.append(value)
            write(output/file,value)
            report_paths.append(dict(file=file,sha256=sha(output/file),source='new scalar training fit'))
            report.update(reports=report_paths,completed_cases=len(completed),wall_seconds=time.monotonic()-started)
            write(output/'result.json',report)
        expected_count=4 if args.phase=='pilot' else 80
        if len(completed)!=expected_count or any(not r['passed'] for r in completed):
            raise ValueError('Required roster incomplete')
        if time.monotonic()>deadline:
            raise TimeoutError('Campaign cap exceeded during final case')
        if args.phase=='full':
            report['summary']=aggregate(completed)
        report.update(passed=True,reports=report_paths,completed_cases=len(completed),
                      historical_floor_checks=6*len(completed),wall_seconds=time.monotonic()-started,
                      cumulative_wall_seconds=pilot_seconds+time.monotonic()-started)
        report.pop('active_case',None)
        write(output/'result.json',report)
        return 0
    except Exception as exc:
        report.update(passed=False,error_type=type(exc).__name__,error=str(exc),wall_seconds=time.monotonic()-started)
        write(output/'result.json',report)
        return 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['pilot','full'],required=True)
    parser.add_argument('--radial',required=True)
    parser.add_argument('--build-receipt',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--pilot')
    parser.add_argument('--acknowledge-reviewed-numerical-admission',default='')
    args=parser.parse_args(argv)
    return run(args)


if __name__=='__main__':
    raise SystemExit(main())
