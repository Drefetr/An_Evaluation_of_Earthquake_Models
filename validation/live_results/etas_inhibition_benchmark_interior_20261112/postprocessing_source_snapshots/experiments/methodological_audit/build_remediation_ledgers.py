"""Emit semantic MASTER-ledger claims from frozen postprocessed authorities.

No scientific execution and no MASTER mutation. Every specification below names
its statistic and JSON pointer explicitly; manuscript numbers never select a
source by value matching.
"""
from pathlib import Path
import argparse,hashlib,json,math,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts import verify_claims as V

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))

class Ledger:
    def __init__(self,source,prefix):
        self.source=source;self.data=json.loads(source.read_bytes());self.prefix=prefix;self.claims=[];self.keys=set()
        if not self.data['passed']:raise ValueError('postprocessed authority not passed')
        if sha(ROOT/self.data['postprocessing_source'])!=self.data['postprocessing_source_sha256']:raise ValueError('postprocessing source changed')
    def add(self,key,pointer,display,locations,component,transformation='decimal rounding to displayed precision',role='manuscript_binding'):
        if key in self.keys:raise ValueError('duplicate semantic specification '+key)
        self.keys.add(key);raw=V.resolve(self.data,pointer)
        c=dict(id=self.prefix+'-'+key,bundled_source=self.source.relative_to(ROOT).as_posix(),source_path=self.source.relative_to(ROOT).as_posix(),source_sha256=sha(self.source),json_pointer=pointer,resolved_source_value=raw,display=str(display),transformation=transformation,json_value_kind='numeric_scalar',ledger_role=role,final_display_locations=locations,component=component,qualification='Completed accepted remote calculation; explicit semantic field, fixed saved fits and verified upstream authority pins.',status='source_bound',binding_kind='exact_json_pointer',value_semantics='transformed_authority_scalar',reconciliation_status='verified_at_declared_granularity')
        c['value']=V.transformed(raw,c,self.data)
        if not V.equal_display(c['value'],c):raise ValueError(('invalid display',key,raw,display))
        if role=='manuscript_binding' and not locations:raise ValueError('missing semantic display location')
        self.claims.append(c)
    def group(self,key,pointer,locations,point=True,ci=True,p=True,precision=3):
        data=V.resolve(self.data,pointer)
        if point:self.add(key+'-total',pointer+'/total',f"{data['total']:.{precision}f}",locations,key+' total log-score contrast in nats')
        if ci:
            for i,side in enumerate(('lower','upper')):self.add(key+'-ci-'+side,pointer+'/ci95_total/'+str(i),f"{data['ci95_total'][i]:.3f}",locations,key+' paired bootstrap 95% interval '+side+' endpoint')
        if p:self.add(key+'-permutation-p',pointer+'/paired_sign_permutation_p',f"{data['paired_sign_permutation_p']:.5f}",locations,key+' two-sided paired sign-flip reference p-value')
    def save(self):
        path=self.source.parent/'ledger_claims.json';write(path,dict(schema='remediation_semantic_claim_additions_v1',claims=self.claims,postprocessed_authority_sha256=sha(self.source),builder_source_sha256=sha(Path(__file__))))
        return path

def uncertainty(source):
    L=Ledger(source,'uncertainty-20261111');d=L.data
    raw=json.loads((ROOT/d['authority']).read_bytes())
    if sha(ROOT/d['authority'])!=d['authority_sha256']:raise ValueError('uncertainty upstream pin changed')
    nz=['chapters/08_score_uncertainty.tex'];ca=['chapters/11_score_uncertainty.tex'];li=['chapters/13_score_uncertainty.tex'];locations={'NZ_shared_minus_ML':nz,'CA_OC_minus_EP':ca,'CA_LIplus_total_minus_floor':li}
    for i,r in enumerate(d['rows']):
        prefix=r['contrast'].lower()+'-'+r['case'];p='/rows/'+str(i);loc=locations[r['contrast']]
        L.add(prefix+'-total',p+'/point',f"{r['point']:.3f}",loc,prefix+' held-out total contrast in nats')
        for j,side in enumerate(('lower','upper')):L.add(prefix+'-ci-'+side,p+'/ci95/'+str(j),f"{r['ci95'][j]:.3f}",loc,prefix+' paired bootstrap interval '+side+' endpoint')
        L.add(prefix+'-permutation-p',p+'/permutation_p',f"{r['permutation_p']:.5f}",loc,prefix+' paired sign-flip p-value')
        # Sign-test statistics are retained as source inventory, not falsely
        # attached to the manuscript's different sign-flip statistic.
        L.add(prefix+'-sign-p-inventory',p+'/sign_p',str(r['sign_p']),[],prefix+' binomial sign-test p-value',role='source_inventory_only')
    L.group('ca-joint-pooled','/pooled/CA_OC_minus_EP',ca)
    L.group('ca-location-pooled','/pooled/CA_OC_minus_EP_location',ca)
    L.group('ca-li-pooled','/pooled/CA_LIplus_total_minus_floor',li)
    for days in ('180','365'):
        L.group('ca-joint-pooled-'+days,'/sensitivity/'+days+'/pooled/CA_OC_minus_EP',ca,point=False)
        L.group('ca-li-pooled-'+days,'/sensitivity/'+days+'/pooled/CA_LIplus_total_minus_floor',li,point=False)
        for i,r in enumerate(d['sensitivity'][days]['rows']):
            if r['contrast']=='NZ_shared_minus_ML' and r['case'] in ('fold_65','fold_80'):
                L.group('nz-'+r['case']+'-'+days,'/sensitivity/'+days+'/rows/'+str(i)+'/summary',nz,point=False,p=False)
                if days=='365' and r['case']=='fold_80':L.add('nz-fold80-365-permutation-p','/sensitivity/365/rows/'+str(i)+'/summary/paired_sign_permutation_p','0.015',nz,'NZ Fold 3 annual-block sign-flip p-value')
            if days=='365' and r['contrast']=='CA_LIplus_total_minus_floor' and r['case']=='california_fold_2':L.group('ca-li-F2-365','/sensitivity/365/rows/'+str(i)+'/summary',li,point=False,p=False)
    L.add('nz-firstfold-percent','/NZ_first_fold_fraction','93.7',nz,'NZ Fold 1 share of the total score deficit',dict(operation='multiply',factor=100))
    L.add('nz-firstfold-percent-abstract','/NZ_first_fold_fraction','94',['abstract.tex'],'Rounded NZ Fold 1 share of the total score deficit',dict(operation='multiply',factor=100))
    L.add('nz-pooled-loss-abstract','/pooled/NZ_shared_minus_ML/total','17.62',['abstract.tex'],'Magnitude of the pooled NZ shared-inhibition score loss',dict(operation='negate'))
    L.add('ca-pooled-loss-abstract','/pooled/CA_OC_minus_EP/total','51.05',['abstract.tex'],'Magnitude of the pooled CA joint OC-minus-EP loss',dict(operation='negate'))
    L.add('ca-pooled-loss-rough','/pooled/CA_OC_minus_EP/total','51',ca,'CA joint loss rounded to whole nats',dict(operation='negate'))
    for pointer,display,loc,name in [('/block_days','90',nz+ca+li,'primary calendar block length in days'),('/method_settings/replicates','49999',nz,'paired resampling replicates'),('/method_settings/confidence_percent','95',nz+ca+li,'percentile interval confidence level'),('/method_settings/sensitivity_block_days/0','180',nz+ca+li,'first sensitivity calendar block length in days'),('/method_settings/sensitivity_block_days/1','365',nz+ca+li,'second sensitivity calendar block length in days'),('/numerical_checks/time_orders/0','32',li,'lower checked log-Gauss temporal order'),('/numerical_checks/time_orders/1','64',li,'higher checked log-Gauss temporal order')]:L.add('method-'+pointer.split('/')[-1]+'-'+display,pointer,display,loc,name)
    observed=d['numerical_checks']['max_calendar_block_refinement_change']
    if not observed<1e-11:raise ValueError('printed refinement upper bound does not hold')
    L.add('max-block-refinement-upper-bound','/numerical_checks/max_calendar_block_refinement_change','1e-11',li,'Outward rounded upper bound on maximum block-exposure refinement change in nats',dict(operation='ceil',quantum=1e-11))
    return L.save()

def benchmark(source):
    L=Ledger(source,'epplus-20261111');d=L.data;loc=['chapters/11_epplus_benchmark.tex'];extra=['abstract.tex','chapters/14_discussion_conclusion.tex']
    authority=ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111/summary.json'
    if sha(authority)!=d['authority_sha256']:raise ValueError('benchmark upstream summary changed')
    for relative,expected in d['source_execution_sha256'].items():
        if sha(ROOT/relative)!=expected:raise ValueError('benchmark executed source changed')
    for relative,expected in d['upstream_pins_verified'].items():
        if sha(ROOT/relative)!=expected:raise ValueError('benchmark upstream artifact changed')
    comparison=authority.parent/'baseline_comparison.json'
    if json.loads(comparison.read_bytes())!=d['original_EP_comparison']:raise ValueError('baseline comparison changed')
    for i,r in enumerate(d['rows']):
        path=authority.parent/r['case']/'result.json'
        if sha(path)!=r['result_sha256']:raise ValueError('benchmark row authority changed')
        for field,fmt in [('n_train','d'),('n_test','d'),('sigma0_km','.3f'),('alpha_s','.3f'),('q','.3f'),('eta','.6f'),('gain','+.4f')]:L.add('F'+str(i)+'-'+field,'/rows/'+str(i)+'/'+field,format(r[field],fmt),loc,'EP+ F'+str(i)+' '+field)
        gain=d['original_EP_comparison']['rows'][i]['gain'];L.add('F'+str(i)+'-gain-over-original-EP','/original_EP_comparison/rows/'+str(i)+'/gain',f'{gain:.3f}',loc,'EP+ combined excitation procedure gain over original EP in F'+str(i))
    L.add('total-gain-over-original-EP','/original_EP_comparison/total_gain','69.553',loc+extra,'Three-fold gain of the combined magnitude/background/joint-fitting procedure over original EP')
    L.add('maximum-fitted-attenuation','/eta_max','0',loc+extra,'Maximum fitted magnitude-scaled EP+ attenuation across all three folds; all return to zero')
    L.add('sigma0-lower-search-bound','/sigma0_search_bounds_km/0','2',loc,'Lower search bound for baseline magnitude-scaled spatial radius in km')
    L.add('background-bandwidth','/model_settings/background_bandwidth_km','5',loc,'Inherited training KDE bandwidth in km')
    L.add('background-floor-percent','/model_settings/background_floor_fraction','5',loc,'Uniform background floor percentage',dict(operation='multiply',factor=100))
    L.add('shadow-radius-exponent','/model_settings/shadow_radius_magnitude_exponent','0.5',loc,'Chosen magnitude exponent in rupture-scaled shadow radius')
    L.add('background-iterations-inventory','/model_settings/background_weighting_iterations','5',[],'Number of successive probability-weighted KDE updates, written as five in prose',role='source_inventory_only')
    return L.save()

def validate(paths):
    checks=[]
    for path in paths:
        data=json.loads(path.read_bytes());failure=[]
        for c in data['claims']:
            source=ROOT/c['bundled_source'];raw=json.loads(source.read_bytes())
            if sha(source)!=c['source_sha256']:raise ValueError('claim source hash changed')
            resolved=V.resolve(raw,c['json_pointer']);transformed=V.transformed(resolved,c,raw)
            if not V.equal_display(transformed,c):failure.append(dict(id=c['id'],reason='invalid numeric transformation/display'))
            if c['ledger_role']=='manuscript_binding':
                # ROOT owns canonical copies. Validate against current copies
                # or the specifically generated same-semantic fragment.
                present=False
                for location in c['final_display_locations']:
                    candidate=ROOT/'paper/source'/location
                    if candidate.exists() and V.numeric_value(c['display']) in V.manuscript_numbers(candidate.read_text(encoding='utf-8-sig')):present=True
                if not present:failure.append(dict(id=c['id'],reason='no declared display present in current canonical fragment'))
        checks.append(dict(ledger=path.relative_to(ROOT).as_posix(),claims=len(data['claims']),passed=not failure,failures=failure))
    write(paths[0].parent/'ledger_validation.json',dict(passed=all(r['passed'] for r in checks),checks=checks,verifier_source_sha256=sha(ROOT/'scripts/verify_claims.py')))
    return checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--uncertainty',type=Path,default=ROOT/'validation/live_results/score_uncertainty_remote_v2_20261111/manuscript/typed_claims.json');p.add_argument('--benchmark',type=Path,default=ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111/manuscript/typed_claims.json');a=p.parse_args()
    paths=[uncertainty(a.uncertainty.resolve()),benchmark(a.benchmark.resolve())];checks=validate(paths);print(json.dumps(checks));raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
if __name__=='__main__':main()
