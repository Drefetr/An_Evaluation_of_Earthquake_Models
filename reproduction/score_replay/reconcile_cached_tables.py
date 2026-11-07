"""Reconcile table arithmetic from retained outputs; no model objective or fit.

The expressions in table_links_cached.json are explicit arithmetic links, not
value-matching guesses. Unmapped cells remain uncovered. Native arrays are read
from the two immutable execution artifacts. Cache access is limited to already
stored event labels, times, and training-count metadata.

Usage: python -B reproduction/score_replay/reconcile_cached_tables.py --output NEW.json
Optional --additional-evidence supplies hash-bound actual rows for supplemental
score expressions and profile support lists. Missing rows remain uncovered.
``passed`` means all mapped cells reconcile, not that every table is covered.
"""
from pathlib import Path
import argparse, collections, hashlib, io, json, math, zipfile
import numpy as np

def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))

class MissingEvidence(KeyError):
    """A mapped row has no supplied actual execution evidence."""

def safe(base, relative):
    path=(base/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base.resolve()):raise ValueError('evidence path escapes declared directory')
    return path

def profile_support(group, row):
    """Training-only support from actual replay rows; no expected-score access."""
    if group['model'] not in ('E0_free','I0_free'):raise ValueError('unknown profile model')
    coordinate=3 if group['model']=='E0_free' else 4
    selected_train=row(group['selected_train_row']);selected_test=row(group['selected_test_row'])
    def values(actual):
        pars=actual['parameters'];joint=actual['components']['joint']
        if len(pars)!=coordinate+1 or not all(math.isfinite(v) for v in pars) or not math.isfinite(joint):raise ValueError('nonfinite/malformed profile state')
        nll=actual['native_scalar_components']['joint_nll']
        if not math.isfinite(nll) or abs(nll+joint)>1e-9:raise ValueError('profile joint/NLL identity')
        return pars,-joint
    selected,selected_nll=values(selected_train);other,_=values(selected_test)
    if selected!=other:raise ValueError('selected train/test vector changed')
    threshold=group['descriptive_support_nll_gap']
    if threshold!=2.0:raise ValueError('original two-nat support rule changed')
    grid=group['grid'];nodes=group['nodes']
    if len(nodes)!=len(grid) or len(set(grid))!=len(grid) or [n['index'] for n in nodes]!=list(range(len(grid))):raise ValueError('incomplete profile node roster')
    output=[];supported=[]
    for node,r in zip(nodes,grid):
        if not math.isfinite(r) or node['r']!=r:raise ValueError('profile grid identity')
        train=row(node['rows']['train']);test=row(node['rows']['test'])
        pars,nll=values(train);test_pars,test_nll=values(test)
        if pars!=test_pars or pars[coordinate]!=r:raise ValueError('profile node train/test vector or grid coordinate changed')
        gap=nll-selected_nll;included=gap<=threshold
        if included:supported.append(r)
        output.append(dict(index=node['index'],r=r,train_row=node['rows']['train'],test_row=node['rows']['test'],
                           training_nll=nll,test_nll=test_nll,training_nll_gap=gap,in_support=included,
                           distance_to_threshold=gap-threshold))
    return dict(case=group['case'],model=group['model'],selected_r=selected[coordinate],
                selected_train_row=group['selected_train_row'],selected_test_row=group['selected_test_row'],
                selected_training_nll=selected_nll,threshold=threshold,comparison='training_nll_gap <= threshold',
                support_r=supported,support_display=', '.join(format(r,'.2f')for r in supported)if supported else'none',
                nodes=output,scope='Sparse descriptive training profile; test scores are retained diagnostics and never support-selection operands.')

class Evidence:
    def __init__(self, package, evidence, additional=None, registries=None):
        self.package=package; self.evidence=evidence
        self.registry=read(package/'cached_registry.json')
        self.byid={r['id']:r for r in self.registry['rows']}
        self.registry_base={rid:package for rid in self.byid};self.adapters={rid:self.registry['adapters'][r['adapter']]for rid,r in self.byid.items()}
        self.deltas=read(evidence/'deltas.json')
        self.index={r['id']:r for r in self.deltas['rows']}
        self.zips={};self.rows={};self.arrays={};self.caches={};self.refinements={};self.profiles={};self.profile_groups={};self.additional={};self.additional_path=additional
        for name,spec in read(evidence/'evidence_index.json')['files'].items():
            b=(evidence/name).read_bytes()
            if sha(b)!=spec['sha256'] or len(b)!=spec['bytes']:raise ValueError('evidence identity '+name)
        for relative,pin in (registries or {}).items():
            path=safe(package,relative)
            if sha(path.read_bytes())!=pin:raise ValueError('additional registry changed '+relative)
            registry=read(path)
            for r in registry['rows']:
                rid=r['id']
                if rid in self.byid:raise ValueError('duplicate additional registry row '+rid)
                self.byid[rid]=r;self.registry_base[rid]=path.parent;self.adapters[rid]=registry['adapters'][r['adapter']]
            for group in registry.get('profile_groups',[]):
                key=group['case']+'/'+group['model']
                if key in self.profile_groups:raise ValueError('duplicate profile group')
                self.profile_groups[key]=group
        if additional:
            self.additional=read(additional)['records']
            if set(self.additional)&self.index.keys():raise ValueError('additional evidence cannot replace completed base rows')
            if set(self.additional)-self.byid.keys():raise ValueError('additional evidence has unknown registry rows')

    def additional_bytes(self,rid):
        spec=self.additional[rid];base=self.additional_path.parent
        if ('path'in spec)==('archive'in spec):raise ValueError('choose one actual row file or archive')
        if 'path'in spec:b=safe(base,spec['path']).read_bytes()
        else:
            archive=safe(base,spec['archive']);member=spec['member'];safe(base,member)
            if sha(archive.read_bytes())!=spec['archive_sha256']:raise ValueError('additional archive changed')
            z=self.archive(base,spec['archive'])
            if len(z.namelist())!=len(set(z.namelist())):raise ValueError('duplicate additional archive member')
            b=z.read(member)
        if sha(b)!=spec['sha256']:raise ValueError('additional actual row changed '+rid)
        return b
    def archive(self,base,name):
        p=base/name
        if p not in self.zips:self.zips[p]=zipfile.ZipFile(p)
        return self.zips[p]
    def row(self,rid):
        if rid not in self.rows:
            if rid in self.index:
                s=self.index[rid];b=self.archive(self.evidence,s['execution_artifact']).read(s['result_member'])
                if sha(b)!=s['result_sha256']:raise ValueError('row hash '+rid)
            elif rid in self.additional:b=self.additional_bytes(rid)
            elif rid in self.byid:raise MissingEvidence(rid)
            else:raise ValueError('unknown replay row '+rid)
            r=json.loads(b)
            if r.get('passed')is not True or r.get('status')!='replayed' or r['id']!=rid:raise ValueError('failed row '+rid)
            spec=self.byid[rid];adapter=self.adapters[rid];actual=r['actual']
            for key,pin in {'state_sha256':spec['state']['sha256'],'cache_sha256':spec['cache']['sha256'],
                            'python_source_sha256':adapter['python']['sha256'],'native_source_sha256':adapter['native']['sha256']}.items():
                if actual[key]!=pin:raise ValueError('actual row input/source identity '+rid)
            self.rows[rid]=r['actual']
        return self.rows[rid]
    def array(self,rid,name):
        if rid not in self.arrays:
            row=self.row(rid);s=self.index[rid];a=row['native_array_components']
            member=str(Path(s['result_member']).parent/a['path']).replace('\\','/')
            b=self.archive(self.evidence,s['execution_artifact']).read(member)
            if sha(b)!=a['sha256']:raise ValueError('array hash '+rid)
            with np.load(io.BytesIO(b),allow_pickle=False) as z:self.arrays[rid]={n:z[n] for n in z.files}
        return self.arrays[rid][name]
    def cache(self,rid):
        s=self.byid[rid]['cache'];key=s['sha256']
        if key not in self.caches:
            b=self.archive(self.registry_base[rid],s['archive']).read(s['member'])
            if sha(b)!=key:raise ValueError('cache hash '+rid)
            # Read only labels/times/probabilities, never geometry or objective.
            with np.load(io.BytesIO(b),allow_pickle=False) as z:
                self.caches[key]={k:z[k] for k in ('event_target','event_zone','event_time','event_excess','pi','target_zone','metadata_json') if k in z.files}
        return self.caches[key]
    def refined(self,d,w,train):
        key=(d,w,train)
        if key in self.refinements:return self.refinements[key]
        dc=self.cache(d);wc=self.cache(w);tr=self.cache(train)
        targets=dc['event_target'].astype(int);tz=tr['event_target'].astype(int)
        if not np.array_equal(dc['event_time'],wc['event_time']) or not np.array_equal(dc['event_excess'],wc['event_excess']):raise ValueError('refinement target alignment')
        if not np.array_equal(targets//3,wc['event_target']):raise ValueError('refinement zone alignment')
        nc=np.bincount(tz,minlength=9);nz=nc.reshape(3,3).sum(axis=1)
        q=(nc+.5)/(np.repeat(nz,3)+1.5)
        if not np.allclose(q.reshape(3,3).sum(axis=1),1,rtol=0,atol=1e-12):raise ValueError('refinement q normalization')
        wlp=self.array(w,'event_log_target_intensity');wlg=self.array(w,'event_log_ground_intensity');wlz=self.array(w,'event_log_zone_intensity')
        we=self.array(w,'target_integrated_intensity');de=self.array(d,'target_integrated_intensity')
        dlp=self.array(d,'event_log_target_intensity');dlg=self.array(d,'event_log_ground_intensity');dlz=self.array(d,'event_log_zone_intensity')
        refp=wlp+np.log(q[targets]);refe=q*np.repeat(we,3)
        within=math.fsum(np.log(q[targets]));wE=math.fsum(we);dE=math.fsum(de)
        wmark=self.row(w)['components']['M'];dmark=self.row(d)['components']['M']
        refjoint=math.fsum(wlp)-wE+wmark+within
        v={'P':math.fsum(dlp-refp),'C':math.fsum(refe)-dE,
           'timing':(math.fsum(dlg)-dE)-(math.fsum(wlg)-wE),
           'zone':math.fsum(dlz-dlg)-math.fsum(wlz-wlg),
           'within':math.fsum(dlp-dlz)-within,'M':dmark-wmark,
           'joint':math.fsum(dlp)-dE+dmark-refjoint,'n_events':len(targets)}
        self.refinements[key]=v;return v
    def evaluate(self,e):
        op=e['op']
        if op=='profile':
            key=e['group']
            if key not in self.profiles:
                group=self.profile_groups[key];value=profile_support(group,self.row)
                selected_tolerance=self.byid[group['selected_train_row']]['absolute_tolerances']['joint']
                for node in value['nodes']:
                    bound=selected_tolerance+self.byid[node['train_row']]['absolute_tolerances']['joint']
                    node.update(replay_difference_allowance_nats=bound,
                                membership_stable_under_replay_allowance=abs(node['distance_to_threshold'])>bound)
                self.profiles[key]=value
            return self.profiles[key][e['field']]
        if op=='constant':return e['value']
        if op=='sum':return math.fsum(self.evaluate(t) for t in e['terms'])/e.get('divisor',1)
        if op=='scale':return e['weight']*self.evaluate(e['value'])
        if op=='wins':return sum(self.evaluate(t)>e['threshold'] for t in e['contrasts'])
        if op=='exp':return math.exp(self.evaluate(e['value']))
        if op=='refined':return self.refined(e['d_row'],e['w_row'],e['train_row'])[e['field']]
        rid=e['row'];kind=e['kind']
        if kind=='components':return self.row(rid)['components'][e['field']]
        if kind=='native_scalar':return self.row(rid)['native_scalar_components'][e['field']]
        if kind=='native_array':return float(self.array(rid,e['field'])[e['index']])
        if kind=='parameters':return self.row(rid)['parameters'][e['index']]
        if kind=='cache_count':return int(np.sum(self.cache(rid)[e['field']]==e['index']))
        if kind=='cache_metadata':
            v=json.loads(str(self.cache(rid)['metadata_json'].item()))
            for key in e['field'].split('/'):v=v[key]
            return v
        raise ValueError('unknown expression '+repr(e))

def reconcile(repo,links_path,evidence,output,additional=None):
    links=read(links_path); data=Evidence(repo/'reproduction/score_replay',evidence,additional,links.get('additional_registry_sha256'))
    if sha((repo/'reproduction/score_replay/cached_registry.json').read_bytes())!=links['registry_sha256']:raise ValueError('registry changed')
    for name,h in links['source_sha256'].items():
        if sha((repo/name).read_bytes())!=h:raise ValueError('manuscript source changed '+name)
    rows=[];counts=collections.Counter();failed=[]
    for table in links['tables']:
        cells=[]
        for c in table['cells']:
            item={k:v for k,v in c.items() if k!='expression'}
            if 'expression' not in c:
                item['status']='uncovered';counts['uncovered_cells']+=1
            else:
                try:value=data.evaluate(c['expression'])
                except MissingEvidence as exc:
                    item.update(status='uncovered',uncovered_reason='Mapped actual replay output not supplied',missing_replay_row=str(exc.args[0]));counts['uncovered_cells']+=1;cells.append(item);continue
                if c.get('display_type')=='profile_support_list':
                    agreed=value==c['display']
                    item.update(recomputed=value,semantic_display_agrees=agreed,arithmetic_reconciled=agreed,status='reconciled'if agreed else'mismatch')
                    counts['mapped_cells']+=1;counts['semantic_support_cells']+=1
                    if not agreed:failed.append({'table':table['id'],'cell':c['id'],'display':c['display'],'recomputed':value})
                    cells.append(item);continue
                v=float(value)
                if not math.isfinite(v):raise ValueError('nonfinite table arithmetic')
                delta=v-c['display_value']; rounding=c['rounding_half_unit']
                # Display rounding and arithmetic identity are reported separately.
                exact_rounding=abs(delta)<=rounding+1e-15
                reconciled=abs(delta)<=rounding+1e-9
                item.update(recomputed=v,delta_from_display=delta,display_rounding_agrees=exact_rounding,
                            arithmetic_allowance_nats=1e-9,arithmetic_reconciled=reconciled,
                            status='reconciled' if reconciled else 'mismatch')
                counts['mapped_cells']+=1
                if not exact_rounding:counts['display_roundoff_cells']+=1
                if not reconciled:failed.append({'table':table['id'],'cell':c['id'],'display':c['display'],'recomputed':v,'delta':delta})
            cells.append(item)
        status='not_numeric_score_table' if not cells else 'numeric_cells_reconciled' if all(c['status']=='reconciled' for c in cells) else 'partial' if any(c['status']=='reconciled' for c in cells) else 'uncovered'
        rows.append({'id':table['id'],'source_file':table['source_file'],'status':status,'source_rows':table['source_rows'],'cells':cells})
    result={'schema':'cached_table_reconciliation_v2','passed':not failed,'all_chapter_tables_covered':counts['uncovered_cells']==0,'scope':'Explicit named numeric cells and sparse-profile support-list semantics. Missing actual rows remain uncovered; no model evaluation or fit.',
            'links_sha256':sha(links_path.read_bytes()),'evidence_index_sha256':sha((evidence/'evidence_index.json').read_bytes()),
            'tolerances':{'original_row_functional_absolute_nats':1e-6,'arithmetic_allowance_nats':1e-9,'display_rounding':'Half of final displayed decimal/scientific unit; zero integers require exact-zero up to separately reported arithmetic allowance.'},
            'counts':dict(counts,tables=len(rows)),'table_status_counts':dict(collections.Counter(t['status'] for t in rows)),
            'additional_evidence_sha256':sha(additional.read_bytes())if additional else None,
            'additional_registry_sha256':links.get('additional_registry_sha256',{}),
            'profile_reconstructions':data.profiles,'mismatches':failed,'tables':rows}
    with output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--links',type=Path,default=Path(__file__).with_name('table_links_cached.json'));p.add_argument('--evidence',type=Path);p.add_argument('--additional-evidence',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=reconcile(a.repo.resolve(),a.links.resolve(),(a.evidence or a.repo/'validation/reproductions/score_replay_20261107/cached').resolve(),a.output.resolve(),a.additional_evidence.resolve()if a.additional_evidence else None);print(json.dumps({k:v for k,v in r.items() if k not in ('tables','mismatches','profile_reconstructions')}));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
