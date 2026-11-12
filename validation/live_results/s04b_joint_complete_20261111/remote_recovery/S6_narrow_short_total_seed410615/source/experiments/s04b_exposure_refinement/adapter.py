"""Explicit optimizer-callback-only refinement; frozen model/fitter stay intact."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import time
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from experiments.s04b_joint_nuisance import fit, model, checkpoint as persistence


def require(value, message):
    if not value: raise ValueError(message)


def same(a, b):
    return persistence.dumps(a,sort_keys=True,separators=(',',':')) == persistence.dumps(b,sort_keys=True,separators=(',',':'))


def diagnostic_json(value):
    """Retain rejected diagnostic operands as explicit tags, never JSON NaN."""
    if isinstance(value, np.ndarray):return diagnostic_json(value.tolist())
    if isinstance(value, np.generic):return diagnostic_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):return {'nonfinite': 'nan' if math.isnan(value) else 'positive_infinity' if value>0 else 'negative_infinity'}
    if isinstance(value, dict):return {k:diagnostic_json(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):return [diagnostic_json(v) for v in value]
    return value


def emit(path, record):
    with Path(path).open('a',encoding='utf-8',newline='\n') as f:
        f.write(persistence.dumps(diagnostic_json(record))+'\n');f.flush();os.fsync(f.fileno())


def coarse_packet(exc, phase):
    """Only locals of the actual frozen full-exposure guard qualify."""
    if type(exc) is not ArithmeticError or str(exc) != 'Nonfinite or negative full exposure':return None
    tb=exc.__traceback__;frame=None
    while tb is not None:
        if tb.tb_frame.f_code is model.Phase.evaluate.__code__:frame=tb.tb_frame
        tb=tb.tb_next
    if frame is None:return None
    values=frame.f_locals
    if values.get('self') is not phase or any(k not in values for k in ('P','E','joint','gradient','theta','model','order')):return None
    P,E,joint,M=map(float,(values['P'],values['E'],values['joint'],phase.M))
    gradient=np.asarray(values['gradient'],dtype=float)
    if not all(math.isfinite(v) for v in (P,E,joint,M)) or E>=-1e-9 or gradient.shape!=(8,) or not np.isfinite(gradient).all():return None
    return dict(score=dict(P=P,E=E,C=-E,M=M,joint=joint,nll=-joint),gradient=gradient.tolist(),
                theta=np.asarray(values['theta'],dtype=float).tolist(),model=values['model'],order=values['order'],
                error_type='ArithmeticError',error=str(exc),origin='experiments/s04b_joint_nuisance/model.py:Phase.evaluate',
                origin_sha256=hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest())


def compare_pair(coarse, fine_score, fine_gradient, theta, name, science):
    fields=('P','E','C','M','joint','nll');g=np.asarray(fine_gradient,dtype=float)
    finite=all(k in fine_score and math.isfinite(fine_score[k]) for k in fields) and g.shape==(8,) and np.isfinite(g).all()
    result=dict(passed=False,finite=bool(finite))
    if not finite:return result
    c=coarse['score'];box=fit.bounds(science,name);dims=len(box)
    pc=fit.projected_gradient(theta[:dims],coarse['gradient'][:dims],box)
    pf=fit.projected_gradient(theta[:dims],g[:dims],box)
    delta=abs(fine_score['joint']-c['joint'])
    scaled=float(np.max(np.abs(pc-pf)/np.maximum(1.,np.maximum(np.abs(pc),np.abs(pf))),initial=0))
    identities=fine_score['C']==-fine_score['E'] and fine_score['joint']==fine_score['P']-fine_score['E']+fine_score['M'] and fine_score['nll']==-fine_score['joint']
    same_point=fine_score['P']==c['P'] and fine_score['M']==c['M']
    result.update(projected_coarse=pc.tolist(),projected_fine=pf.tolist(),absolute_joint_delta=delta,
                  projected_gradient_scaled_delta=scaled,score_identities=bool(identities),same_P_M=bool(same_point),
                  fine_exposure_nonnegative=fine_score['E']>=0,
                  joint_tolerance=science['quadrature']['joint_absolute_tolerance'],
                  gradient_tolerance=science['quadrature']['selected_training_gradient_scaled_tolerance'])
    result['passed']=bool(identities and same_point and fine_score['E']>=0 and delta<=result['joint_tolerance'] and scaled<=result['gradient_tolerance'])
    return result


class RefinedPhase:
    def __init__(self, phase, owner, phase_name):
        self._phase,self._owner,self._name=phase,owner,phase_name
    def __getattr__(self, name):return getattr(self._phase,name)
    def _original(self,theta,name,order,require_gradient,context):
        key='|'.join(map(str,(self._name,name,order,context,require_gradient)))
        count=self._owner.evaluations[key];count['attempted']+=1
        started=time.monotonic()
        try:
            answer=self._phase.evaluate(theta,name,order,require_gradient=require_gradient)
        except BaseException:
            count['errors']+=1;raise
        finally:self.last_call_elapsed=time.monotonic()-started
        count['returned']+=1;return answer
    def evaluate(self,theta,name='null',order=8,require_gradient=True):
        owner=self._owner;token=owner.callback
        context='optimizer' if token is not None else 'original_support'
        try:
            return self._original(theta,name,order,require_gradient,context)
        except ArithmeticError as exc:
            if token is None or self._name!='train' or order!=8 or owner.refining:return_error= True
            else:return_error=not (token['phase'] is self and token['model']==name and same(token['theta'],np.asarray(theta).tolist()))
            if return_error:raise
            packet=coarse_packet(exc,self._phase)
            if packet is None:raise
            require(packet['model']==name and packet['order']==8 and same(packet['theta'],token['theta']), 'Frozen exception identity differs')
            owner.refinement_sequence+=1;event_id=owner.refinement_sequence
            context_record=dict(phase='train',**{k:v for k,v in token.items() if k!='phase'})
            coarse_seconds=self.last_call_elapsed
            owner.log_refinement('refinement_start',event_id=event_id,context=context_record,theta=packet['theta'],coarse=packet,coarse_seconds=coarse_seconds)
            owner.refining=True;owner.callback=None
            try:
                fine,gf=self._original(theta,name,16,True,'refinement_fine')
                compared=compare_pair(packet,fine,gf,np.asarray(theta),name,owner.science)
                owner.log_refinement('refinement_end',event_id=event_id,context=context_record,
                    theta=packet['theta'],fine=dict(score=fine,gradient=np.asarray(gf).tolist()),
                    comparison=compared,accepted=compared['passed'],effective_order=16,
                    coarse_seconds=coarse_seconds,fine_seconds=self.last_call_elapsed)
                if not compared['passed']:
                    owner.refinement_rejected+=1
                    raise exc
                owner.refinement_accepted+=1
                return fine,gf
            except BaseException as fine_error:
                if fine_error is not exc:
                    owner.refinement_rejected+=1
                    owner.log_refinement('refinement_end',event_id=event_id,context=context_record,
                        theta=packet['theta'],accepted=False,error_type=type(fine_error).__name__,error=str(fine_error),
                        coarse_seconds=coarse_seconds,fine_seconds=self.last_call_elapsed)
                raise
            finally:
                owner.callback=token;owner.refining=False


class Adapter:
    def __init__(self,science,output,partial=None,trace=None,optimizer=minimize):
        self.science,self.output,self.partial,self.trace=science,Path(output),partial,trace
        self.real_optimizer=optimizer;self.current=None;self.callback=None;self.refining=False
        self.refinement_sequence=0;self.refinement_accepted=0;self.refinement_rejected=0
        self.evaluations=defaultdict(Counter);self.optimizer_calls=[];self.arm_calls=[]
        self.phase_constructions=[];self.phases={};self.reuse_entries=[];self.check_calls=[]
        for name in ('refinement_events.jsonl','execution_calls.jsonl'):
            p=self.output/name;require(not p.exists(),'Fresh amendment log required');p.touch()
        if partial is not None:self.validate_partial()

    def log(self,event,**record):emit(self.output/'execution_calls.jsonl',dict(event=event,**record))
    def log_refinement(self,event,**record):emit(self.output/'refinement_events.jsonl',dict(event=event,**record))

    def validate_partial(self):
        p=self.partial;require(p['case_id']=='S6_narrow_short_total_seed410603' and p['passed'] is False and p['outcomes']==[] and not p.get('training_selections_frozen',False),'Wrong partial case')
        require(list(p['fits'])==['null','LI','LIplus_immigrant','LIplus_inclusive'],'Partial arm roster differs')
        require(len(self.trace)==60,'Partial trace census differs')
        for start,end in zip(self.trace[::2],self.trace[1::2]):
            require(start['event']=='attempt_start' and end['event']=='attempt_end' and all(same(start[k],end[k]) for k in ('model','method','start_index','initial_parameters')),'Partial trace pair differs')
        for name,arm in p['fits'].items():
            records=[{k:v for k,v in r.items() if k not in ('event','model')} for r in self.trace if r['event']=='attempt_end' and r['model']==name]
            require(same(records,arm['records']),'Partial fit/trace records differ')
            if name!='LIplus_inclusive':
                require(arm['passed'] is True and arm['resolved_starts']==[True]*8 and p['training_checks'][name]['passed'] is True,'Incomplete reused arm/check')
                require(arm['selected']==arm['candidates'][arm['selected_state_index']],'Reused selection differs')
            else:
                require(arm['passed'] is False and arm['status']=='unknown_starts' and arm['resolved_starts']==[True]*4+[False] and arm['not_run_starts']==[5,6,7],'Wrong partial total suffix')
                require(len(arm['candidates'])==5 and [r['state_index'] for r in arm['candidates']]==list(range(5)) and [r['start_index'] for r in arm['candidates']]==[-1,0,1,2,3],'Wrong total candidate prefix')
                for i in range(4):
                    r=records[i];c=arm['candidates'][i+1]
                    require(r['start_index']==i and r['method']=='L-BFGS-B' and r['success'] is True and same(c['parameters'],r['parameters']) and same(c['score'],r['fresh_score']) and same(c['gradient'],r['gradient']),'Total prefix candidate differs')
                for r,method in zip(records[4:],('L-BFGS-B','Powell')):
                    require(r['start_index']==4 and r['method']==method and r['status']=='exception' and r['error_type']=='ArithmeticError' and r['error']=='Nonfinite or negative full exposure','Wrong retained failed start')

    def wrap_phase(self,phase,start,end):
        label='train' if (start,end)==(30,395) else 'test' if (start,end)==(395,760) else None
        require(label is not None and label not in self.phases,'Wrong or repeated phase')
        wrapped=RefinedPhase(phase,self,label);self.phases[label]=wrapped
        self.phase_constructions.append(dict(start=start,end=end,returned=True));return wrapped

    def callback_checkpoint(self,checkpoint):
        def wrapped(record):
            if record['event']=='attempt_start':self.current=copy.deepcopy(record)
            checkpoint(record)
        return wrapped

    def optimizer(self,objective,initial,*,jac,bounds,method,options):
        current=self.current;require(current is not None,'Optimizer without declared attempt')
        name=current['model'];start=current['start_index'];key=(name,start,method)
        expected={k:self.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')} if method=='L-BFGS-B' else self.science['solver']['powell']
        require(key not in self.optimizer_calls and method==current['method'] and same(initial,current['initial_parameters']) and same(bounds,fit.bounds(self.science,name)) and same(options,expected) and jac==(method=='L-BFGS-B'),'Changed/repeated optimizer recipe')
        self.optimizer_calls.append(key);attempts=returns=0;returned=False
        self.log('optimizer_start',model=name,start_index=start,method=method,initial_parameters=np.asarray(initial).tolist(),bounds=bounds,options=options,jac=jac)
        def callback(x):
            nonlocal attempts,returns
            require(self.callback is None and not self.refining,'Nested optimizer objective')
            attempts+=1;theta=fit.expand(x,name).tolist()
            self.callback=dict(phase=self.phases['train'],model=name,start_index=start,method=method,callback_index=attempts,theta=theta)
            try:
                value=objective(x);returns+=1;return value
            finally:self.callback=None
        try:
            answer=self.real_optimizer(callback,initial,jac=jac,bounds=bounds,method=method,options=options)
            returned=True;return answer
        finally:
            self.callback=None
            self.log('optimizer_end',model=name,start_index=start,method=method,returned=returned,
                     callback_attempts=attempts,callback_returns=returns,evaluation_census=dict(self.evaluations))

    def fit_arm(self,phase,name,science,eligible,checkpoint):
        require(phase is self.phases.get('train') and same(science,self.science),'Wrong fit phase/protocol')
        require(name==['null','LI','LIplus_immigrant','LIplus_inclusive'][len(self.arm_calls)],'Changed arm order')
        self.arm_calls.append(name);wrapped=self.callback_checkpoint(checkpoint)
        if self.partial is not None and name!='LIplus_inclusive':
            for r in self.trace:
                if r['model']==name:checkpoint(copy.deepcopy(r))
            self.reuse_entries.append(dict(kind='complete_arm',model=name,pointer='/fits/'+name))
            self.log('reuse_arm',model=name,physical_optimizer_calls=0)
            return copy.deepcopy(self.partial['fits'][name])
        if self.partial is not None:
            from .partial_fit import resume_partial_fit
            arm=self.partial['fits'][name]
            for r in self.trace:
                if r['model']==name and r['start_index']<4:checkpoint(copy.deepcopy(r))
            self.reuse_entries.append(dict(kind='total_prefix',model=name,candidate_indices=list(range(5)),record_indices=list(range(4)),prior_failed_record_indices=[4,5]))
            self.log('reuse_total_prefix',model=name,physical_optimizer_calls=0,candidate_indices=list(range(5)),record_indices=list(range(4)))
            return resume_partial_fit(phase,name,science,eligible,arm,wrapped,self.optimizer)
        return fit.fit_arm(phase,name,science,eligible,wrapped,self.optimizer)

    def fine_check(self,phase,name,arm,science):
        require(self.callback is None and not self.refining,'Selected check inside callback')
        self.check_calls.append(name)
        if self.partial is not None and name!='LIplus_inclusive':
            require(same(arm,self.partial['fits'][name]),'Reused complete fit changed')
            self.reuse_entries.append(dict(kind='selected_training_check',model=name,pointer='/training_checks/'+name))
            self.log('reuse_selected_training_check',model=name,physical_evaluations=0)
            return copy.deepcopy(self.partial['training_checks'][name])
        return fit.fine_check(phase,name,arm,science)

    def historical_floor(self,original,phase,case,old,expected,states,fits,label):
        require(self.callback is None,'Historical floor inside callback')
        if self.partial is not None and label=='train':
            self.reuse_entries.append(dict(kind='historical_training_floor',pointer='/fits/null/candidates/0/score'))
            self.log('reuse_historical_training_floor',physical_evaluations=0)
            return copy.deepcopy(self.partial['fits']['null']['candidates'][0]['score']),copy.deepcopy([v for v in self.partial['floor_checks'] if v['phase']=='train'])
        return original(phase,case,old,expected,states,fits,label)

    def receipt(self):
        return dict(arm_calls=self.arm_calls,selected_check_calls=self.check_calls,
            physical_optimizer_calls=[list(x) for x in self.optimizer_calls],evaluation_census=dict(self.evaluations),
            refinement_started=self.refinement_sequence,refinement_accepted=self.refinement_accepted,
            refinement_rejected=self.refinement_rejected,reuse_entries=self.reuse_entries,
            phase_constructions=self.phase_constructions,callback_active=self.callback is not None,refinement_active=self.refining)
