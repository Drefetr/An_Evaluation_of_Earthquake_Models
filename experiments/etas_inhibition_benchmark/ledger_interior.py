"""Bind corrected interior-start benchmark displays; do not mutate MASTER."""
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from experiments.methodological_audit.build_remediation_ledgers import Ledger
from scripts import verify_claims as V

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_bytes((json.dumps(d,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();root=a.directory.resolve();source=root/'manuscript/typed_claims.json';L=Ledger(source,'epplus-interior-20261112');d=L.data;loc=['chapters/11_epplus_benchmark.tex'];extra=['abstract.tex','chapters/14_discussion_conclusion.tex']
    authority=root/'summary.json';s=json.loads(authority.read_bytes());audit=root/'interior_start_audit.json'
    if sha(authority)!=d['authority_sha256'] or not s['all_final_power_interior_start_coverage_passed'] or not json.loads(audit.read_bytes())['passed']:raise ValueError('corrected authority not independently accepted')
    for rel,expected in d['source_execution_sha256'].items():
        if sha(ROOT/rel)!=expected:raise ValueError('executed source changed '+rel)
    for rel,expected in d['upstream_pins_verified'].items():
        if sha(ROOT/rel)!=expected:raise ValueError('upstream artifact changed '+rel)
    if json.loads((root/'baseline_comparison.json').read_bytes())!=d['original_EP_comparison']:raise ValueError('comparison changed')
    for i,r in enumerate(d['rows']):
        if sha(root/r['case']/'result.json')!=r['result_sha256']:raise ValueError('case changed')
        for field,fmt in [('n_train','d'),('n_test','d'),('sigma0_km','.3f'),('alpha_s','.3f'),('q','.3f'),('eta','.6f'),('gain','+.4f')]:L.add('F'+str(i)+'-'+field,'/rows/'+str(i)+'/'+field,format(r[field],fmt),loc,'EP+ F'+str(i)+' '+field)
        gain=d['original_EP_comparison']['rows'][i]['gain'];L.add('F'+str(i)+'-gain-over-original-EP','/original_EP_comparison/rows/'+str(i)+'/gain',f'{gain:.3f}',loc,'Combined magnitude/background/joint-fitting/spatial-normalization procedure gain over original EP in F'+str(i))
    total=d['original_EP_comparison']['total_gain'];L.add('total-gain-over-original-EP','/original_EP_comparison/total_gain',f'{total:.3f}',loc+extra,'Three-fold gain of combined magnitude/background/joint-fitting/spatial-normalization procedure over archived finite-rectangle-normalized EP')
    L.add('maximum-fitted-attenuation','/eta_max',format(d['eta_max'],'.6g'),loc+extra,'Maximum fitted attenuation across all three folds')
    L.add('sigma0-lower-search-bound','/sigma0_search_bounds_km/0','2',loc,'Lower search bound for baseline magnitude-scaled spatial radius in km')
    L.add('background-bandwidth','/model_settings/background_bandwidth_km','5',loc,'Inherited training KDE bandwidth in km')
    L.add('background-floor-percent','/model_settings/background_floor_fraction','5',loc,'Uniform background floor percentage',dict(operation='multiply',factor=100))
    L.add('shadow-radius-exponent','/model_settings/shadow_radius_magnitude_exponent','0.5',loc,'Chosen magnitude exponent in shadow radius')
    L.add('background-iterations-inventory','/model_settings/background_weighting_iterations','5',[],'Number of successive probability-weighted KDE updates, written as five in prose',role='source_inventory_only')
    L.add('positive-start-count-inventory','/prescribed_positive_start_count','3',[],'Fresh strictly positive attenuation starts at every final training resolution, written as three in prose',role='source_inventory_only')
    path=L.save();ledger=json.loads(path.read_bytes());ledger.update(builder_source=Path(__file__).relative_to(ROOT).as_posix(),builder_source_sha256=sha(Path(__file__)),helper_source_sha256=sha(ROOT/'experiments/methodological_audit/build_remediation_ledgers.py'),independent_start_audit_sha256=sha(audit));write(path,ledger)
    old=json.loads((ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111/manuscript/ledger_claims.json').read_bytes())['claims'];mapping=[]
    for c in old:
        key=c['id'].removeprefix('epplus-20261111-');new='epplus-interior-20261112-'+key
        if new not in {r['id'] for r in ledger['claims']}:raise ValueError('missing replacement '+key)
        mapping.append(dict(old_id=c['id'],new_id=new))
    old_u=ROOT/'validation/live_results/etas_baseline_uncertainty_20261111/manuscript/ledger_claims.json';new_u=root/'baseline_uncertainty/manuscript/ledger_claims.json'
    if new_u.exists():
        before=json.loads(old_u.read_bytes())['claims'];after=json.loads(new_u.read_bytes())['claims']
        for c in before:
            key=c['id'].removeprefix('epplus-baseline-uncertainty-20261111-');new='epplus-baseline-uncertainty-interior-20261112-'+key
            if new not in {r['id'] for r in after}:raise ValueError('missing interval replacement '+key)
            mapping.append(dict(old_id=c['id'],new_id=new))
    checks=[];fragment=(root/'manuscript/11_epplus_benchmark.tex').read_text()
    for c in ledger['claims']:
        raw=json.loads((ROOT/c['bundled_source']).read_bytes());resolved=V.resolve(raw,c['json_pointer']);value=V.transformed(resolved,c,raw)
        if sha(ROOT/c['bundled_source'])!=c['source_sha256'] or not V.equal_display(value,c):raise ValueError('claim binding failed '+c['id'])
        if c['ledger_role']=='manuscript_binding' and V.numeric_value(c['display']) not in V.manuscript_numbers(fragment):raise ValueError('display missing from new fragment '+c['id'])
        checks.append(dict(id=c['id'],passed=True))
    receipt=dict(passed=True,claims=len(ledger['claims']),interval_claims=len(json.loads(new_u.read_bytes())['claims']) if new_u.exists() else 0,old_claims_replaced=len(mapping),replacement_mapping=mapping,new_claims_added=[c['id'] for c in ledger['claims'] if c['id'] not in {m['new_id'] for m in mapping}],claim_source_and_display_checks=checks,builder_source_sha256=sha(Path(__file__)))
    write(root/'claim_replacement_mapping.json',receipt);print(json.dumps(dict(passed=True,claims=receipt['claims'],interval_claims=receipt['interval_claims'],old_claims_replaced=len(mapping),ledger=path.relative_to(ROOT).as_posix())))
if __name__=='__main__':main()
