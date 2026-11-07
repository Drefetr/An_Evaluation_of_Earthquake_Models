"""Reconcile explicit regional table expressions from actual replay artifacts.

No native objective, optimizer, generator or original expected-score file is
called. Missing or failed replay records remain incomplete. The evidence manifest
may locate immutable JSON reports directly or inside a retained execution ZIP.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import zipfile

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs,digest,pointer,resolve,write_new
from reproduction.score_replay.inventory import tables


class Evidence:
    def __init__(self,package,manifest_path,links):
        self.package=package;self.manifest_path=manifest_path
        self.manifest=json.loads(manifest_path.read_bytes());self.links=links
        self.records={};self.used={};self.registries={}
        for name,expected in links['registry_sha256'].items():
            path=package/name/'registry.json';raw=path.read_bytes()
            if digest(raw)!=expected:raise ValueError('mapping registry changed: '+name)
            self.registries[name]=json.loads(raw)

    def record(self,name):
        if name not in self.records:
            spec=self.manifest['records'].get(name)
            if spec is None:raise KeyError('Actual replay evidence missing: '+name)
            path=Path(spec.get('archive',spec.get('path')))
            if not path.is_absolute():path=resolve(self.manifest_path.parent,path.as_posix())
            if 'archive' in spec:
                if spec.get('archive_sha256') and digest(path.read_bytes())!=spec['archive_sha256']:
                    raise ValueError('execution archive SHA mismatch: '+name)
                member=spec['member']
                if member.startswith('/') or '..' in Path(member).parts or '\\' in member:raise ValueError('invalid evidence member')
                with zipfile.ZipFile(path) as z:
                    if sum(i.filename==member for i in z.infolist())!=1:raise ValueError('ambiguous evidence member')
                    raw=z.read(member)
            else:raw=path.read_bytes()
            if digest(raw)!=spec['sha256']:raise ValueError('actual replay record SHA mismatch: '+name)
            value=json.loads(raw)
            if value.get('passed') is not True:raise ValueError('actual replay record failed: '+name)
            if 'id' in value and (value['id']!=name or value.get('status')!='replayed'):
                raise ValueError('actual replay row identity/status mismatch: '+name)
            self.records[name]=value;self.used[name]=dict(sha256=digest(raw),evidence=spec)
        return self.records[name]

    def evaluate(self,e):
        op=e['op']
        if op=='constant':return float(e['value']),0.
        if op=='sum':
            values=[self.evaluate(x) for x in e['terms']]
            return math.fsum(x[0] for x in values),math.fsum(x[1] for x in values)
        if op=='scale':
            value,error=self.evaluate(e['value']);return e['weight']*value,abs(e['weight'])*error
        if op=='multiply':
            a,ae=self.evaluate(e['left']);b,be=self.evaluate(e['right'])
            return a*b,abs(a)*be+abs(b)*ae+ae*be
        if op=='divide':
            value,error=self.evaluate(e['numerator']);denominator,de=self.evaluate(e['denominator'])
            if de or denominator<=0:raise ValueError('ratio requires an exact positive denominator')
            return value/denominator,error/denominator
        if op=='statistic':
            values=[self.evaluate(x) for x in e['values']]
            if not values:raise ValueError('empty statistic roster')
            x=[v[0] for v in values];errors=[v[1] for v in values];name=e['statistic']
            if name=='count':return len(x),0.
            if name=='positive_count':return sum(v>0 for v in x),0.
            if name=='mean':return statistics.mean(x),statistics.mean(errors)
            if name=='median':return statistics.median(x),max(errors)
            if name=='mcse':return statistics.stdev(x)/math.sqrt(len(x)),2*max(errors)
            raise ValueError('unknown statistic')
        if op=='field':
            if not e['pointer'].startswith('/actual/'):raise ValueError('table field must select actual evaluated output')
            value=pointer(self.record(e['record']),e['pointer'])
        elif op=='select':
            if e['pointer'] not in ('/absolute_rows','/contrasts','/comparison/comparisons'):
                raise ValueError('only current aggregate/contrast arrays can be selected')
            if e['field'] in ('original_gain','expected','reference'):raise ValueError('reference values cannot be table operands')
            source=pointer(self.record(e['record']),e['pointer'])
            rows=[r for r in source if all(r.get(k)==v for k,v in e['where'].items())]
            if len(rows)!=1:raise ValueError('nonunique semantic table link: '+str(e['where']))
            value=rows[0][e['field']]
        elif op=='state':
            # Input metadata is allowed only after the actual replay identifies
            # exactly that state; this does not certify its original selection.
            registry=self.registries[e['registry']]
            row=next(r for r in registry['rows'] if r['id']==e['row'])
            actual=self.record(e['row'])['actual']
            if actual['state_sha256']!=row['state']['sha256']:raise ValueError('input metadata state mismatch')
            value=pointer(Inputs(self.package/e['registry']).json(row['state']),e['pointer'])
        else:raise ValueError('unknown table operation '+op)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('table expression did not yield a finite number')
        return float(value),e['absolute_tolerance']


def reconcile(package,manifest_path,links_path,output):
    if output.exists():raise FileExistsError(output)
    raw=links_path.read_bytes();links=json.loads(raw);repo=package.parents[1]
    evidence=Evidence(package,manifest_path,links);reports=[];file_tables={}
    for table in links['tables']:
        rel=table['source_file']
        if rel not in file_tables:file_tables[rel]=tables((repo/rel).read_bytes().decode('utf-8'))
        ordinal=int(table['id'].rsplit(':',1)[1])-1
        if file_tables[rel][ordinal]['body_sha256']!=table['body_sha256']:
            raise ValueError('current source table changed: '+table['id'])
        cells=[]
        for cell in table['cells']:
            result={k:cell[k] for k in ('id','source_row_index','column_index','numeric_token_index','display','display_value','rounding_half_unit')}
            try:
                value,bound=evidence.evaluate(cell['expression']);delta=abs(value-cell['display_value'])
                limit=bound+cell['rounding_half_unit'];passed=delta<=limit+1e-12
                result.update(passed=passed,status='reconciled' if passed else 'failed',actual=value,absolute_delta=delta,functional_tolerance=bound,rounding_agreement=delta<=cell['rounding_half_unit']+1e-12,allowed_absolute_delta=limit)
            except KeyError as exc:result.update(passed=False,status='not_run',reason=str(exc))
            except Exception as exc:result.update(passed=False,status='failed',reason=type(exc).__name__+': '+str(exc))
            cells.append(result)
        reports.append(dict(table_id=table['id'],mapped_cells=len(cells),reconciled_cells=sum(c['passed'] for c in cells),not_run_cells=sum(c['status']=='not_run' for c in cells),failed_cells=sum(c['status']=='failed' for c in cells),passed=bool(cells) and all(c['passed'] for c in cells),scope=table['mapping_scope'],uncovered_reason=table.get('uncovered_reason'),cells=cells))
    aliases=[];prior_path=package/'prior_s05_inventory.json'
    if prior_path.exists():
        prior=json.loads(prior_path.read_bytes())
        for row in prior['observed_score_aliases']:
            checks=[]
            for name,expression in row['expressions'].items():
                check=dict(field=name,expected=row['score_reference'][name],passed=False)
                try:
                    value,bound=evidence.evaluate(expression);delta=abs(value-check['expected'])
                    check.update(actual=value,absolute_delta=delta,absolute_tolerance=bound,passed=delta<=bound+1e-12,status='reconciled' if delta<=bound+1e-12 else 'failed')
                except KeyError as exc:check.update(status='not_run',reason=str(exc))
                except Exception as exc:check.update(status='failed',reason=type(exc).__name__+': '+str(exc))
                checks.append(check)
            aliases.append(dict(model=row['model'],origin=row['origin'],replay_row_id=row['replay_row_id'],passed=all(c['passed'] for c in checks),checks=checks))
    mapped=[c for t in reports for c in t['cells']]
    result=dict(schema='regional_table_reconciliation_v1',passed=bool(mapped) and all(c['passed'] for c in mapped),entire_task_complete=False,mapped_cells=len(mapped),reconciled_cells=sum(c['passed'] for c in mapped),not_run_cells=sum(c['status']=='not_run' for c in mapped),failed_cells=sum(c['status']=='failed' for c in mapped),links_sha256=digest(raw),evidence_manifest_sha256=digest(manifest_path.read_bytes()),reconciler_sha256=digest(Path(__file__).read_bytes()),actual_record_pins=evidence.used,tables=reports,scope='Only explicitly mapped score/count cells. Functional tolerance is propagated separately from manuscript display rounding. Historical optimizer execution and omitted/pre-replayed table scope are not certified by this arithmetic route.')
    result['s05_observed_aliases']=aliases
    result['s05_inventory_sha256']=digest(prior_path.read_bytes()) if prior_path.exists() else None
    result['passed']=result['passed'] and all(x['passed'] for x in aliases)
    write_new(output,result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--links',type=Path,default=Path(__file__).with_name('table_links_regional.json'));args=p.parse_args()
    r=reconcile(Path(__file__).parent.resolve(),args.evidence.resolve(),args.links.resolve(),args.output.resolve())
    print(json.dumps({k:v for k,v in r.items() if k not in ('tables','actual_record_pins')}));return 0 if r['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
