"""Constructed joint-likelihood controls; never reads scientific histories."""
import copy,hashlib,json,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from threadpoolctl import threadpool_limits
from engine.cpu_build import build_shared
from experiments.s04b_joint_nuisance import model,fit,run,checkpoint

def fixture(native):
    t=np.array([.1,.4,.4,.9]);xy=np.array([[2.,3.],[8.,8.],[4.,8.],[6.,2.]])
    q=np.array([.2,.5,.1,.6]);rect=np.array([[0.,10.,0.,10.]])
    geom=model.Geometry();sigma=2.;Z=geom.masses(xy,rect,sigma,2).ravel()/100
    kde=np.array([[1.5,2.],[7.5,8.]]);kw=np.array([.4,.6]);kZ=geom.masses(kde,rect,3.,2).ravel()
    def background(query):
        rr=((query[:,None,:]-kde[None,:,:])**2).sum(axis=2)
        return .1/100+.9*((1+rr/9)**-2/kZ)@kw
    target=t>=.25;et=t[target];exy=xy[target]
    distance=((exy[:,None,:]-xy[None,:,:])**2).sum(axis=2)
    arrays=dict(parent_time=t,parent_xy=xy,parent_excess=q,parent_fertility=.3*np.exp(1.4*q),parent_normalizer=Z,
      parent_exposure_lo=np.maximum(.25-t,0),parent_exposure_hi=1.1-t,event_time=et,event_xy=exy,
      event_x=2*et/1.2-1,event_excess=q[target],event_background_density=background(exy),
      event_parent_density=(1+distance/sigma**2)**-2/Z[None,:]/100)
    m=dict(start=.25,end=1.1,T0=1.2,beta=2.,sigma=sigma)
    phase=model.Phase(arrays,m,{},native)
    phase.plan_info={'fixture':True}
    for order,count in((8,32),(16,48)):
        z,w=np.polynomial.legendre.leggauss(count);X,Y=np.meshgrid(5+5*z,5+5*z,indexing='ij')
        space=np.column_stack([X.ravel(),Y.ravel()]);area=(25*np.outer(w,w)).ravel();b=background(space)
        area=area/(area@b)
        edges=[.25,.4,.9,1.1];times=[];weights=[]
        for lo,hi in zip(edges[:-1],edges[1:]):times.extend((lo+hi)/2+(hi-lo)/2*z);weights.extend((hi-lo)/2*w)
        times=np.array(times);weights=np.array(weights)
        r2=((space[:,None,:]-xy[None,:,:])**2).sum(axis=2)
        phase._grids[order]=dict(r2=r2,coeff=(1+r2/sigma**2)**-2*arrays['parent_fertility'][None,:]/Z[None,:]/100,
            b=b,area=area,t=times,w=weights,estimate=0,space_nodes=len(space),time_nodes=len(times),parents=len(t))
    phase.plan=lambda order:phase._grids[order]
    return phase

def direct_components(phase,theta,name,order=16):
    """Independent direct parent sums and full exposure, no native recurrence."""
    a,d,n,logc,p,eta,logell,logpsi=theta;c=math.exp(logc);ell=math.exp(logell);psi=math.exp(logpsi)
    arr=phase.a;grid=phase.plan(order);gamma=0 if name=='LI'else.75*math.log(10)
    lag=grid['t'][:,None]-arr['parent_time'][None,:];past=lag>0
    temporal=(p-1)/c*np.exp(-p*np.log1p(np.maximum(lag,0)/c))*past
    trigger=grid['coeff']@temporal.T
    stress_radial=np.exp(gamma*arr['parent_excess'])[None,:]/(1+grid['r2']/ell**2)**2
    stress=stress_radial@(np.exp(-np.maximum(lag,0)/psi)*past).T
    B=grid['b'][:,None]*np.exp(a+d*(2*grid['t']/phase.m['T0']-1))[None,:]
    if name=='null':intensity=B+n*trigger
    elif name=='LIplus_inclusive':intensity=(B+n*trigger)*np.exp(-eta*stress)
    else:intensity=B*np.exp(-eta*stress)+n*trigger
    E=float(grid['area']@intensity@grid['w'])
    P=0.
    for i,t in enumerate(arr['event_time']):
        H=G=0.
        for j,s in enumerate(arr['parent_time']):
            if s>=t:continue
            H+=arr['parent_fertility'][j]*(p-1)/c*(1+(t-s)/c)**(-p)*arr['event_parent_density'][i,j]
            G+=math.exp(gamma*arr['parent_excess'][j]-(t-s)/psi)/(1+phase.event_r2[i,j]/ell**2)**2
        B=math.exp(a+d*arr['event_x'][i])*arr['event_background_density'][i]
        value=B+n*H if name=='null'else(B+n*H)*math.exp(-eta*G)if name=='LIplus_inclusive'else B*math.exp(-eta*G)+n*H
        P+=math.log(value)
    return dict(P=P,E=E,C=-E,M=phase.M,joint=P-E+phase.M)

class JointLikelihood(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.thread_limit=threadpool_limits(limits=2);cls.thread_limit.__enter__()
        cls.temp=tempfile.TemporaryDirectory(prefix='joint_constructed_')
        cls.receipt=build_shared(model.HERE/'attenuation.cpp',Path(cls.temp.name)/'native',dependency_root=model.HERE)
        cls.native=model.Native(cls.receipt['library'])
    @classmethod
    def tearDownClass(cls):
        # Windows keeps loaded DLL files mapped; retained temp location is harmless.
        try:cls.temp.cleanup()
        except PermissionError:pass
        cls.thread_limit.__exit__(None,None,None)
    def setUp(self):
        self.phase=fixture(self.native)
        self.theta=np.array([-1.2,.15,.3,math.log(.07),1.4,.4,math.log(3.),math.log(.25)])
    def test_components_match_independent_full_quadrature(self):
        for name in('null',*fit.MODELS):
            actual,_=self.phase.evaluate(self.theta,name,16);expected=direct_components(self.phase,self.theta,name)
            for key in expected:self.assertAlmostEqual(actual[key],expected[key],delta=2e-7,msg=name+'/'+key)
            self.assertAlmostEqual(actual['P']+actual['C']+actual['M'],actual['joint'],delta=1e-12)
    def test_all_shared_and_inhibition_gradients(self):
        for name in('null',*fit.MODELS):
            _,g=self.phase.evaluate(self.theta,name,8)
            for j in range(5 if name=='null'else 8):
                h=1e-5;x=self.theta.copy();y=x.copy();x[j]+=h;y[j]-=h
                fd=(self.phase.evaluate(x,name,8)[0]['nll']-self.phase.evaluate(y,name,8)[0]['nll'])/(2*h)
                self.assertAlmostEqual(g[j],fd,delta=2e-6*max(1.,abs(fd)),msg=name+'/'+str(j))
    def test_eta_zero_is_same_exact_floor(self):
        self.theta[5]=0;floor,_=self.phase.evaluate(self.theta,'null')
        for name in fit.MODELS:
            actual,_=self.phase.evaluate(self.theta,name)
            for key in floor:self.assertEqual(actual[key],floor[key])
    def test_zero_branching_gradients(self):
        self.theta[2]=0
        for name in fit.MODELS:
            _,g=self.phase.evaluate(self.theta,name)
            self.assertEqual(g[3],0);self.assertEqual(g[4],0)
            h=1e-6;x=self.theta.copy();x[2]+=h
            fd=(self.phase.evaluate(x,name)[0]['nll']-self.phase.evaluate(self.theta,name)[0]['nll'])/h
            self.assertAlmostEqual(g[2],fd,delta=3e-4)
    def test_strict_past_tied_events(self):
        self.assertEqual(int(np.sum(self.phase.lag[0]>0)),1)
        self.assertEqual(int(np.sum(self.phase.lag[1]>0)),1)
    def test_shared_parameters_actually_change_exposure(self):
        base=self.phase.evaluate(self.theta,'LIplus_inclusive')[0]
        for j in range(5):
            q=self.theta.copy();q[j]+=.02
            self.assertGreater(abs(self.phase.evaluate(q,'LIplus_inclusive')[0]['E']-base['E']),1e-7)
    def test_rectangle_primitive_independent_cartesian_integral(self):
        got=model.Geometry().masses(np.array([[.3,.4]]),np.array([[0.,1.,0.,2.]]),.7,2)[0,0]
        ref=quad(lambda x:quad(lambda y:(1+((x-.3)**2+(y-.4)**2)/.7**2)**-2,0,2,epsabs=1e-12)[0],0,1,epsabs=1e-12)[0]
        self.assertAlmostEqual(got,ref,delta=1e-11)
    def test_analytic_omori_exposure_gradients(self):
        lo=np.array([0.,.1,1.]);hi=lo+.9;logc=math.log(.07);p=1.2
        j,jc,jp=model.exposure(lo,hi,logc,p);h=1e-5
        for k,expected in enumerate((jc,jp)):
            plus=model.exposure(lo,hi,logc+(h if k==0 else 0),p+(h if k==1 else 0))[0]
            minus=model.exposure(lo,hi,logc-(h if k==0 else 0),p-(h if k==1 else 0))[0]
            np.testing.assert_allclose((plus-minus)/(2*h),expected,rtol=1e-7,atol=1e-9)
    def test_time_grid_does_not_change_with_c(self):
        grid=self.phase.plan(8)['t'].copy();self.theta[3]+=1
        self.phase.evaluate(self.theta,'LIplus_inclusive');np.testing.assert_array_equal(grid,self.phase.plan(8)['t'])
    def test_nonfinite_parameters_rejected(self):
        self.theta[0]=float('nan')
        with self.assertRaises(ValueError):self.phase.evaluate(self.theta)
    def test_exact_historical_floor_checks_are_six_not_five(self):
        theta=[math.log(.2),.2,.35,math.log(.05),1.3,0.,math.log(30),math.log(7)]
        score,_=self.phase.evaluate(theta,'null');old={'phases':{k:{'historical':score}for k in('train','test')}}
        fits={m:{'floor':[0,1,1]}for m in fit.MODELS};states={m:[{'pars':[0,1,1]}]for m in fit.MODELS}
        expected={'phase_values':{key:{m:[[score['nll'],0,0,0,0,score['P']]]for m in fit.MODELS}for key in('order16_train','order32_test')}}
        checks=[]
        for phase in('train','test'):checks+=run.historical_floor(self.phase,{},old,expected,states,fits,phase)[1]
        self.assertEqual(len(checks),6);self.assertEqual(len(checks)*80,480)
        expected['phase_values']['order16_train']['LI'][0][0]+=2e-9
        with self.assertRaises(ValueError):run.historical_floor(self.phase,{},old,expected,states,fits,'train')

    def test_constructed_full_case_json_roundtrip_and_no_training_resume(self):
        """Real native fixture scores, fixed-return test optimizer; never study inputs."""
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp);root=repo/'reproduction/synthetic';root.mkdir(parents=True)
            olddir=repo/'validation/live_results/methodological_20261106/refitted_floor';olddir.mkdir(parents=True)
            np.savez(root/'rows.npz',rows=np.zeros((4,4)))
            for name,value in [('states.json',{}),('expected.json',{}),('receipt.json',{'counters':{}})]:checkpoint.write(root/name,value)
            checkpoint.write(olddir/'constructed.json',{})
            case=dict(case_id='constructed',regime=4,seed=1,history='rows.npz',fits={},states='states.json',expected='expected.json',generator_receipt='receipt.json',n_train=3,n_test=3)
            protocol=run.read(model.HERE/'protocol.json')
            theta=np.array([math.log(.2),.2,.35,math.log(.05),1.3,0.,math.log(30),math.log(7)])
            generator=SimpleNamespace(MATCHED_NAMES=['fixture'],ROSTER={'fixture':(None,None,0.,30.,7.)},
                Law=lambda *a:SimpleNamespace(a=theta[0],d=theta[1],n=theta[2],c=.05,p=theta[4],r=.7),
                fitting_metadata=lambda law:{'beta':2.,'sigma_km':2.})
            def historical(phase,case,old,expected,states,fits,label):
                score,_=phase.evaluate(theta,'null')
                return score,[dict(phase=label,model=m,actual_nll=score['nll'],expected_nll=score['nll'],absolute_delta=0.,tolerance=1e-9)for m in fit.MODELS]
            oldscore=self.phase.evaluate(theta,'null')[0]
            comparison=[dict(model=m,gate=g,saved_procedure_joint=oldscore['joint'])for m in fit.MODELS for g in(('raw',)if m=='LI'else('raw','BIC'))]
            def fitted(phase,name,protocol,eligible,callback):
                def fixed(fun,x,**kwargs):
                    values=eligible[:len(x)];value=fun(values)
                    return SimpleNamespace(x=np.array(values),fun=value[0]if isinstance(value,tuple)else value,success=True,status=0,message='constructed fixed-return optimizer',nfev=1,nit=0)
                return fit.fit_arm(phase,name,protocol,eligible,callback,optimizer=fixed)
            output=repo/'first';output.mkdir()
            with patch.object(run,'REPO',repo),patch.object(run,'compare_historical',return_value=comparison),patch.object(run,'historical_floor',side_effect=historical),patch.object(model,'phase_from_rows',return_value=self.phase),patch.object(run,'fit_arm',side_effect=fitted):
                actual=run.case_run(case,{'generator':generator},self.native,protocol,output,math.inf)
            self.assertTrue(actual['passed'],actual.get('error'));self.assertEqual(len(actual['outcomes']),5)
            self.assertEqual(run.read(output/'constructed.json'),json.loads(checkpoint.dumps(actual)))
            self.assertTrue(any(isinstance(v,np.bool_)for row in actual['outcomes']for v in row.values()))
            frozen=copy.deepcopy(actual);frozen.update(passed=False,status='running',outcomes=[])
            frozen['floor_checks']=[v for v in frozen['floor_checks']if v['phase']=='train']
            frozen['plan_dimensions']={'train':frozen['plan_dimensions']['train']}
            keys=run.read(model.HERE/'checkpoint_repair.json')['training_payload_keys']
            policy=dict(case_id='constructed',training_payload_keys=keys,attempts_sha256=run.sha(output/'constructed.attempts.jsonl'),
                training_payload_canonical_sha256=hashlib.sha256(checkpoint.canonical_training(frozen,keys)).hexdigest())
            checkpoint.validate_training(frozen,output/'constructed.attempts.jsonl',policy)
            changed=copy.deepcopy(frozen);changed['n_train']+=1
            with self.assertRaises(ValueError):checkpoint.validate_training(changed,output/'constructed.attempts.jsonl',policy)
            badtrace=repo/'changed.attempts.jsonl';badtrace.write_bytes((output/'constructed.attempts.jsonl').read_bytes()+b'\n')
            with self.assertRaises(ValueError):checkpoint.validate_training(frozen,badtrace,policy)
            checkpoint.write(repo/'checkpoint_repair.json',policy);checkpoint.write(repo/'frozen.json',frozen)
            resumed=repo/'resumed';resumed.mkdir();resume=dict(checkpoint=repo/'frozen.json',trace=output/'constructed.attempts.jsonl',prior_seconds=17.,provenance={'attempts_sha256':policy['attempts_sha256']})
            phase_calls=[]
            def test_only(rows,gm,start,end,*args):
                phase_calls.append((start,end));self.assertEqual((start,end),(395,760));return self.phase
            with patch.object(run,'REPO',repo),patch.object(run,'HERE',repo),patch.object(run,'compare_historical',return_value=comparison),patch.object(run,'historical_floor',side_effect=historical),patch.object(model,'phase_from_rows',side_effect=test_only),patch.object(run,'fit_arm',side_effect=AssertionError('Repeated training fit')):
                second=run.case_run(case,{'generator':generator},self.native,protocol,resumed,math.inf,resume)
            self.assertTrue(second['passed'],second.get('error'));self.assertEqual(phase_calls,[(395,760)])
            self.assertEqual(second['fits'],actual['fits']);self.assertEqual(second['training_checks'],actual['training_checks'])
            self.assertEqual(second['outcomes'],actual['outcomes']);self.assertEqual(run.sha(resumed/'constructed.attempts.jsonl'),policy['attempts_sha256'])
            self.assertEqual(second['prior_training_attempt_seconds'],17.)

class PersistenceControls(unittest.TestCase):
    def test_numpy_scalars_arrays_and_nonfinite_rejection(self):
        value={'flag':np.bool_(True),'count':np.int64(4),'score':np.float64(1.25),'array':np.array([True,False])}
        self.assertEqual(json.loads(checkpoint.dumps(value)),{'flag':True,'count':4,'score':1.25,'array':[True,False]})
        for value in (np.float64('nan'),np.float64('inf'),np.array([float('nan')]),object()):
            with self.assertRaises((ValueError,TypeError)):checkpoint.dumps({'value':value})
    def test_failed_serialization_preserves_last_checkpoint_and_no_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'case.json';checkpoint.write(path,{'passed':False,'fits':4});before=path.read_bytes()
            with self.assertRaises(TypeError):checkpoint.write(path,{'bad':object()})
            self.assertEqual(path.read_bytes(),before);self.assertEqual(list(Path(temp).glob('*.tmp')),[])
    def test_failed_replace_preserves_checkpoint_and_cleans_own_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'case.json';checkpoint.write(path,{'value':1});before=path.read_bytes()
            stale=Path(temp)/'unrelated.tmp';stale.write_text('preserve')
            with patch.object(checkpoint.os,'replace',side_effect=OSError('constructed replacement failure')):
                with self.assertRaises(OSError):checkpoint.write(path,{'value':2})
            self.assertEqual(path.read_bytes(),before);self.assertEqual(list(Path(temp).glob('*.tmp')),[stale])
            checkpoint.write(path,{'value':np.int64(3)});self.assertEqual(run.read(path),{'value':3})
    def test_interrupt_cleans_own_temporary_and_keeps_last_good_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'case.json';checkpoint.write(path,{'passed':False});before=path.read_bytes()
            with patch.object(checkpoint.os,'replace',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):checkpoint.write(path,{'passed':True})
            self.assertEqual(path.read_bytes(),before);self.assertEqual(list(Path(temp).glob('*.tmp')),[])

class PolicyControls(unittest.TestCase):
    def setUp(self):self.protocol=json.loads((model.HERE/'protocol.json').read_text())
    def test_eight_shared_start_budgets_and_null_candidate(self):
        null=np.array([-2.,.1,.4,math.log(.05),1.3,0.,math.log(30),math.log(7)])
        for name in('null',*fit.MODELS):
            s=fit.starts(self.protocol,20,name,null);self.assertEqual(len(s),8)
            if name!='null':np.testing.assert_array_equal(s[0][:5],null[:5]);self.assertTrue(all(x[5]>0 for x in s[1:]))
    def test_projected_gradient_at_bounds(self):
        np.testing.assert_array_equal(fit.projected_gradient([0.,1.,.5],[2.,-3.,4.],[(0,1)]*3),[0,0,4])
    def test_strict_win_and_separate_nearzero(self):
        f={'selected':{'kind':'optimizer','parameters':[0]*8},'selected_state_index':2}
        result=run.select_prediction(f,'raw',True,[0]*8,{'joint':0.},{'joint':5e-10})
        self.assertTrue(result['new_win']);self.assertTrue(result['near_zero']);self.assertFalse(result['robust_positive'])
    def test_exact_floor_return_uses_stored_score(self):
        f={'selected':{'kind':'optimizer','parameters':[1]*8},'selected_state_index':2};null={'joint':-10.}
        result=run.select_prediction(f,'BIC',False,[0]*8,null,{'joint':-9.999999999})
        self.assertIs(result['score'],null);self.assertEqual(result['new_gain'],0.);self.assertFalse(result['new_win']);self.assertEqual(result['selected_state_index'],0)
    def fake_phase(self):
        class Fake:
            a={'event_time':np.zeros(10)}
            def evaluate(self,theta,name,order,**kwargs):
                g=np.zeros(8);g[:5]=2*np.array(theta[:5]);g[5]=2*theta[5]if name!='null'else 0
                value=float(np.dot(theta[:5],theta[:5])+(theta[5]**2 if name!='null'else 0))
                return dict(nll=value,joint=-value,P=-value,E=0.,C=0.,M=0.),g
        return Fake()
    def solver_result(self,fun,x,success):
        value=fun(x);value=value[0]if isinstance(value,tuple)else value
        return SimpleNamespace(x=np.asarray(x),fun=value,success=success,status=0 if success else 1,message='fake fixture',nfev=1,nit=0)
    def test_null_candidate_and_all_resolved_returns_retained(self):
        phase=self.fake_phase();theta=np.array([-2.,0.,.3,math.log(.05),1.3,0.,math.log(30),math.log(7)])
        result=fit.fit_arm(phase,'LI',self.protocol,theta,optimizer=lambda fun,x,**kw:self.solver_result(fun,x,True))
        self.assertTrue(result['passed']);self.assertEqual(len(result['records']),8);self.assertEqual(len(result['candidates']),9)
        self.assertEqual(result['candidates'][0]['kind'],'new_null_floor')
    def test_unresolved_starts_remain_unknown(self):
        theta=np.array([-2.,0.,.3,math.log(.05),1.3,0.,math.log(30),math.log(7)])
        result=fit.fit_arm(self.fake_phase(),'LI',self.protocol,theta,optimizer=lambda fun,x,**kw:self.solver_result(fun,x,False))
        self.assertFalse(result['passed']);self.assertEqual(result['status'],'unknown_starts');self.assertEqual(len(result['records']),2)
        self.assertEqual(result['not_run_starts'],list(range(1,8)))
    def test_primary_arithmetic_failure_retained_before_powell(self):
        theta=np.array([-2.,0.,.3,math.log(.05),1.3,0.,math.log(30),math.log(7)])
        def optimize(fun,x,method,**kw):
            if method=='L-BFGS-B':raise ArithmeticError('constructed derivative overflow')
            return self.solver_result(fun,x,True)
        result=fit.fit_arm(self.fake_phase(),'LI',self.protocol,theta,optimizer=optimize)
        self.assertTrue(result['passed']);self.assertEqual(len(result['records']),16)
        self.assertEqual(result['records'][0]['error_type'],'ArithmeticError')
    def test_timeout_never_retried(self):
        records=[];theta=np.array([-2.,0.,.3,math.log(.05),1.3,0.,math.log(30),math.log(7)])
        def timeout(*a,**k):raise TimeoutError('constructed resource cap')
        with self.assertRaises(TimeoutError):fit.fit_arm(self.fake_phase(),'LI',self.protocol,theta,records.append,optimizer=timeout)
        self.assertEqual(len(records),2);self.assertEqual(records[-1]['error_type'],'TimeoutError')
    def test_wilson_all_wins(self):
        interval=run.wilson(20,20);self.assertAlmostEqual(interval[0],.8388748419,delta=1e-9);self.assertAlmostEqual(interval[1],1.)
    def test_missing_reports_cannot_be_completed(self):
        with self.assertRaises(ValueError):run.aggregate([],self.protocol)

if __name__=='__main__':unittest.main()
