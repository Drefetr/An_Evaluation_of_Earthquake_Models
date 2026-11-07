"""Five retained training-support evaluations; never an optimizer or test score.

The externally supervised launcher owns admission. Exit zero means the diagnostic
completed, not that repeated checks were identical or that recovery may proceed.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import platform
import time
import numpy as np
from experiments.s04b_joint_nuisance import fit
from experiments.s04b_joint_recovery import driver
from experiments.s04b_joint_recovery.adapter import check_comparison

EXPECTED_CALLS = [('null',8),('null',8),('null',16),('LI',8),('LI',16)]


class RetainedPhase:
    def __init__(self,phase,records,save):
        self.phase,self.records,self.save=phase,records,save
    def evaluate(self,theta,model='null',order=8,require_gradient=True):
        number=len(self.records)
        driver.require(number<len(EXPECTED_CALLS) and (model,order)==EXPECTED_CALLS[number]
            and require_gradient is True,'Undeclared diagnostic evaluation')
        row=dict(number=number+1,model=model,order=order,parameters=np.asarray(theta).tolist(),returned=False)
        self.records.append(row);self.save()
        try:
            score,gradient=self.phase.evaluate(theta,model,order,require_gradient)
            row.update(returned=True,score=copy.deepcopy(score),gradient=np.asarray(gradient).tolist())
            return score,gradient
        except BaseException as exc:
            row.update(error_type=type(exc).__name__,error=str(exc));raise
        finally:self.save()


def checks(phase,case,old,expected,states,fits,partial,protocol,result,save):
    phase=RetainedPhase(phase,result['evaluations'],save)
    _,floor=driver.frozen.historical_floor(phase,case,old,expected,states,fits,'train')
    result['historical_floor']=check_comparison(floor,partial['floor_checks']);save()
    for name in ('null','LI'):
        actual=fit.fine_check(phase,name,partial['fits'][name],protocol)
        result['training_checks'][name]=check_comparison(actual,partial['training_checks'][name]);save()
    driver.require(len(result['evaluations'])==5 and all(r['returned'] for r in result['evaluations']),
        'Incomplete diagnostic evaluation roster')
    result['equality_passed']=result['historical_floor']['exact_match'] and all(r['exact_match'] for r in result['training_checks'].values())


def run(args):
    started=time.monotonic();out=Path(args.output).resolve()
    driver.require(not out.is_relative_to(driver.REPO),'Fresh diagnostic output must be outside checkout')
    out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='joint_training_support_diagnostic_v1',passed=False,diagnostic_complete=False,
        scientific_completion=False,equality_passed=None,evaluations=[],training_checks={},optimizer_calls=0,held_out_calls=0)
    def save():
        result['wall_seconds']=time.monotonic()-started;driver.write(out/'result.json',result)
    save()
    try:
        driver.require(0<float(args.wall_seconds)<=60,'Diagnostic wall allowance must be positive and at most sixty seconds')
        deadline=started+float(args.wall_seconds)
        policy=driver.verify_protocol();p=policy['predecessor'];prior=Path(args.prior).resolve()
        index_path=prior/'science/index.json';partial_path=prior/'science/cases'/(policy['sequence'][40]+'.json')
        library=prior/'build/attenuation.so';build_path=prior/'build/build_receipt.json'
        for path,pin in [(index_path,p['index_sha256']),(partial_path,p['case_sha256']),
                         (library,p['library_sha256']),(build_path,p['build_receipt_sha256'])]:
            driver.require(driver.sha(path)==pin,'Original diagnostic input differs: '+path.name)
        runtime=driver.frozen.runtime_identity()
        driver.require(runtime['essential']==p['runtime_essential'],'Original scientific runtime required')
        build=driver.read(build_path)
        driver.require(build['passed'] is True and build['source_sha256']==driver.sha(driver.legacy.SCIENCE/'attenuation.cpp'),
            'Original native build provenance differs')
        result.update(source_sha256=driver.source_identity(),runtime=runtime,
            recovery_protocol_sha256=driver.sha(driver.HERE/'recovery_protocol.json'),
            predecessor_index_sha256=driver.sha(index_path),partial_checkpoint_sha256=driver.sha(partial_path),
            library_sha256=driver.sha(library),build_receipt_sha256=driver.sha(build_path),
            processor=platform.processor(),numpy_cpu_features=getattr(np._core._multiarray_umath,'__cpu_features__',{}))
        partial=driver.read(partial_path);protocol=driver.read(driver.legacy.SCIENCE/'protocol.json')
        case=next(c for c in driver.frozen.verify_inputs(protocol) if c['case_id']==partial['case_id'])
        root=driver.REPO/'reproduction/synthetic'
        with np.load(root/case['history'],allow_pickle=False) as z:rows=z['rows'].copy()
        fits={k:driver.read(root/v) for k,v in case['fits'].items()}
        states=driver.read(root/case['states']);expected=driver.read(root/case['expected'])
        oldpath=driver.REPO/'validation/live_results/methodological_20261106/refitted_floor'/(case['case_id']+'.json')
        old=driver.read(oldpath)
        for name,pin in partial['input_sha256'].items():
            path=driver.REPO/name if name.startswith('validation/') else root/name
            driver.require(driver.sha(path)==pin,'Original scientific input changed')
        result.update(case_id=case['case_id'],input_sha256=partial['input_sha256']);save()
        modules=driver.model.archived();G=modules['generator'];name=G.MATCHED_NAMES[case['regime']-4]
        _,bg,eta,ell,psi=G.ROSTER[name];law=G.Law(name,case['seed'],bg,eta,ell,psi)
        gm=G.fitting_metadata(law);native=driver.model.Native(library)
        with driver.legacy.OrderedChunkScheduler() as scheduler:
            delegate=driver.legacy.runner_with_scheduler(scheduler)
            phase=delegate.model.phase_from_rows(rows,gm,30,395,modules,native,deadline)
            checks(phase,case,old,expected,states,fits,partial,protocol,result,save)
        driver.require(time.monotonic()<deadline,'Diagnostic deadline exceeded')
        result.update(passed=True,diagnostic_complete=True,status='diagnostic_complete')
    except BaseException as exc:
        result.update(passed=False,diagnostic_complete=False,status='diagnostic_failed',error_type=type(exc).__name__,error=str(exc))
    finally:
        save()
        if 'deadline' in locals() and time.monotonic()>=deadline:
            result.update(passed=False,diagnostic_complete=False,status='diagnostic_failed',error_type='FinalizationDeadline',error='Diagnostic finalization exceeded allowance');save()
    return 0 if result['diagnostic_complete'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('prior','output'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--wall-seconds',type=float,default=60)
    raise SystemExit(run(parser.parse_args()))
