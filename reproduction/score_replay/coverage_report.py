"""Union actual table-cell reconciliations without evaluating a scientific model.

CLI: coverage_report.py --evidence inputs.json --output fresh.json
The manifest pins plan, inventory, routes and prior evidence. A resource is
{path, sha256, base: repository|manifest}; ZIP resources instead have
{archive, archive_sha256, member, sha256, base}. Paths are relative to that base.
Each cached/regional route requires delta, links, evidence and producer resources;
cached additional evidence requires an `additional` resource. Case routes require
delta, execution, protocol and producer. Optional review resources are retained
as attributed evidence, never turned into an invented independent acceptance.
Optional metadata_dispositions pins explicit per-cell identity/count evidence;
its accepted records are labelled metadata_checked, never score replay.
Prior resources map the exact coverage-plan evidence string to its pinned bytes.
This report is not a likelihood replay and does not upgrade prior scope.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reproduction.score_replay.inventory import tables as parse_tables

NUMBER = re.compile(r'(?<![A-Za-z])[-+]?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?')


def require(value, message):
    if not value: raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def portable(base, name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name,
            'Resource path must be portable and relative')
    parts = name.split('/')
    require(all(p not in ('', '.', '..') for p in parts), 'Noncanonical resource path')
    path = (base/name).resolve()
    require(path.is_relative_to(base.resolve()) and path != base.resolve(), 'Resource escapes base')
    return path


class Resources:
    def __init__(self, repo, manifest_path):
        self.repo = repo.resolve(); self.base = manifest_path.resolve().parent; self.used = {}; self.archive_pins = {}

    def raw(self, spec, role):
        base = self.repo if spec.get('base', 'repository') == 'repository' else self.base
        require(spec.get('base', 'repository') in ('repository', 'manifest'), 'Unknown resource base')
        if 'archive' in spec:
            archive = portable(base, spec['archive'])
            identity=(str(archive),archive.stat().st_size,archive.stat().st_mtime_ns)
            if identity not in self.archive_pins:self.archive_pins[identity]=digest(archive.read_bytes())
            require(self.archive_pins[identity] == spec['archive_sha256'], 'Archive identity: '+role)
            member = spec['member']; portable(Path('.').resolve(), member)
            with zipfile.ZipFile(archive) as source:
                require(source.namelist().count(member) == 1, 'Missing/duplicate ZIP member: '+role)
                data = source.read(member)
        else:
            data = portable(base, spec['path']).read_bytes()
        require(digest(data) == spec['sha256'], 'Resource identity: '+role)
        self.used[role] = dict(spec)
        return data

    def json(self, spec, role):
        return json.loads(self.raw(spec, role), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def finite(value):
    require(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value), 'Nonfinite numeric cell')
    return float(value)


def field_key(cell):
    suffix = 'semantic' if cell.get('display_type') == 'profile_support_list' else str(cell.get('numeric_token_index', 0))
    return f"{cell['source_row_index']}:{cell['column_index']}:{suffix}"


def no_reference_operand(expr):
    if isinstance(expr, list):
        for value in expr: no_reference_operand(value)
    elif isinstance(expr, dict):
        if 'pointer' in expr:
            op=expr.get('op');path=expr['pointer']
            require(isinstance(path,str),'Operand pointer must be a string')
            forbidden=lambda name: name in ('expected','reference','original_gain') or name.startswith(('expected_','reference_'))
            require(not any(forbidden(part) for p in path.split('/')
                            for part in p.replace('~1','/').replace('~0','~').split('/')),
                    'Reference pointer cannot be a score operand')
            if op=='field':
                require(path.startswith('/actual/'),'Field must select an actual evaluated result')
            elif op=='state':
                require(path=='/nuisance/N' and expr.get('absolute_tolerance')==0
                        and isinstance(expr.get('row'),str) and expr['row']
                        and isinstance(expr.get('registry'),str) and expr['registry'],
                        'Only exact replay-bound state count metadata is admitted')
            elif op=='select':
                fields={'/absolute_rows':{'conditional_location','duration_microseconds','inherited_mark','joint','n_anchor_target','n_target','timing','timing_compensator','timing_event'},
                        '/contrasts':{'conditional_location_logscore','joint_logscore','signed_share','target_count','timing_logscore'},
                        '/comparison/comparisons':{'gain'}}
                require(path in fields and expr.get('field') in fields[path]
                        and isinstance(expr.get('record'),str) and expr['record']
                        and isinstance(expr.get('where'),dict) and expr['where'],
                        'Select must use a declared actual aggregate array/field and semantic key')
            else:raise ValueError('Pointer requires a supported operand operation')
        if 'field' in expr:
            require(expr['field'] not in ('expected', 'reference', 'original_gain')
                    and not expr['field'].startswith(('expected_', 'reference_')), 'Reference field cannot be a score operand')
        for value in expr.values(): no_reference_operand(value)


def numeric_text(text):
    # Collapse the paper's wrapped mantissa-times-ten displays before treating
    # the TeX linebreak as the end of a data row. Exponents are not extra cells.
    text=re.sub(r'([-+]?\d+(?:\.\d+)?)\s*\$?\s*(?:\\\\)?\s*\$?\s*\\times\s*10\s*\^\s*\{?([-+]?\d+)\}?',
                lambda m:m[1]+'e'+m[2],text)
    text=re.sub(r'\\shortstack(?:\[[^\]]*\])?\s*\{','{',text)
    # A calendar range dash separates positive year labels, unlike a score sign.
    return re.sub(r'(?<!\d)(\d{4})-(?=\d{4}(?:\D|$))',r'\1 ',text)


def inventory_numeric_fields(table):
    """Inventory literal numeric data cells independently of expression maps.

Textual labels (M1, fold_0, headings and equations containing named variables)
are not numeric data cells. Plain scalars, counts, intervals and numeric lists
are; every token in such a cell is required, including a fraction denominator.
Existing explicitly mapped semantic/complex fields are added separately.
"""
    fields=set()
    for row,line in enumerate(table['source_rows']):
        for column,raw in enumerate(line.split('&')):
            text=re.split(r'\\\\',numeric_text(raw))[0].strip()
            text=text.replace('\\%','%').replace('\\pm','±')
            text=re.sub(r'\\(?:num|texttt|mathrm|textbf|mathbf|ensuremath|textrm|mathsf|mathit)\s*\{([^{}]*)\}',r'\1',text)
            text=text.replace('$','').strip()
            text=numeric_text(text)
            if not NUMBER.search(text):continue
            residue=NUMBER.sub('',text)
            if re.search(r'[^\s\[\](){},;/+%±\-]',residue):continue
            for token,_ in enumerate(NUMBER.finditer(text)):
                fields.add(f'{row}:{column}:{token}')
    return fields


def case_records(resources, execution_spec, execution, role):
    """Verify every retained case, not merely its completion index."""
    records={}
    for entry in execution['cases']:
        identity=entry['case_id'];name=entry['file']
        require(identity not in records and entry.get('passed',True) is True,'Duplicate/failed indexed case')
        require(isinstance(name,str) and name and '/' not in name and '\\' not in name
                and name not in ('.','..') and ':' not in name,'Case report filename is not portable')
        spec=dict(execution_spec,sha256=entry['sha256'])
        key='member' if 'archive' in spec else 'path'
        spec[key]=(PurePosixPath(spec[key]).parent/name).as_posix()
        record=resources.json(spec,role+'/'+identity)
        require(record.get('passed') is True and record.get('case_id')==identity,'Retained case did not pass')
        records[identity]=record
    return records


def source_number(table, row, column, token=0):
    text = table['source_rows'][row].split('&')[column]
    matches = list(NUMBER.finditer(numeric_text(text)))
    require(token < len(matches), 'Cell numeric token missing')
    literal = matches[token].group(); value = float(literal.replace(',', ''))
    mantissa = literal.lower().split('e')[0]
    exponent = int(literal.lower().split('e')[1]) if 'e' in literal.lower() else 0
    places = len(mantissa.split('.')[1]) if '.' in mantissa else None
    half = .5*10**(exponent-places) if places is not None else 0.
    return literal, value, half


def checked_cell(table, mapped, evidence, route, kind):
    key = field_key(mapped)
    result = dict(field=key, route=route, status='not_run', scope='explicit mapped field',
                  source_row_index=mapped['source_row_index'], column_index=mapped['column_index'])
    if mapped.get('expression') is not None:
        no_reference_operand(mapped['expression'])
        if mapped['expression'].get('op') == 'constant': result['scope'] = 'pinned fixed metadata; no likelihood evidence'
    if evidence is None or evidence.get('status') in ('uncovered', 'not_run', 'pending'):
        result['reason'] = (evidence or mapped).get('reason', mapped.get('uncovered_reason', 'No actual mapped output'))
        return result
    require(field_key(evidence) == key, 'Delta cell identity mismatch')
    if evidence.get('status') == 'failed' or evidence.get('passed') is False:
        result.update(status='failed', reason=evidence.get('reason', 'Producer reported failed cell')); return result
    actual = evidence.get('recomputed') if kind == 'cached' else evidence.get('actual')
    if key.endswith(':semantic'):
        source = table['source_rows'][mapped['source_row_index']].split('&')[mapped['column_index']]
        source = re.split(r'\\\\', source)[0].strip()
        passed = isinstance(actual, str) and source == actual and evidence.get('arithmetic_reconciled') is True
        result.update(status='reconciled' if passed else 'failed', actual=actual, display=source,
                      semantic=True, exact_display_match=passed)
        return result
    literal, display, half = source_number(table,mapped['source_row_index'],mapped['column_index'],mapped.get('numeric_token_index',0))
    if mapped.get('display_type')=='six_significant_digits_trailing_zeros_omitted':
        require(format(display,'.6g')==literal.lstrip('+'),
                'Source display is not the declared six-significant-digit format')
        half=.5*10**(math.floor(math.log10(abs(display)))-5) if display else 0.
        declared=finite(mapped['rounding_half_unit'])
        require(abs(declared-half)<=max(math.ulp(declared),math.ulp(half)),
                'Declared six-significant-digit rounding unit differs from source')
    mapped_display=finite(mapped['display_value'])
    # Equivalent mantissa-times-power and scientific-string parsing can differ
    # by one IEEE-754 unit; this is not an additional score tolerance.
    require(abs(display-mapped_display)<=max(math.ulp(display),math.ulp(mapped_display)),
            'Mapping does not identify current manuscript display')
    actual = finite(actual)
    allowance = finite(evidence.get('arithmetic_allowance_nats', 0.) if kind == 'cached' else evidence['functional_tolerance'])
    require(allowance >= 0, 'Negative functional allowance')
    delta = abs(actual-display); limit = half+allowance
    producer_pass = evidence.get('arithmetic_reconciled') is True if kind == 'cached' else evidence.get('passed') is True
    rounding_flags={key:evidence[key] for key in ('display_rounding_agrees','displayed_rounding_matches','exact_display_match') if key in evidence}
    exact_rounding=delta<=half and all(value is not False for value in rounding_flags.values())
    result.update(status='reconciled' if producer_pass and delta <= limit else 'failed',
                  actual=actual, display=literal, absolute_delta=delta, functional_tolerance=allowance,
                  rounding_half_unit=half, allowed_absolute_delta=limit, exact_display_match=exact_rounding,
                  producer_display_rounding_flags=rounding_flags)
    return result


def companion_fields(table, mapped, result):
    """Derive only whole-display tokens and actual wins-roster denominators.

A checked semantic support display covers every token of that very display.
A win denominator is the cardinality of the distinct evaluated contrasts, never
copied from the manuscript numerator or denominator. Unsuccessful source fields
cannot confer successful coverage on their companions.
"""
    row=mapped['source_row_index'];column=mapped['column_index']
    derived=[]
    if result.get('semantic') and result['status']=='reconciled':
        for token,match in enumerate(NUMBER.finditer(result['actual'])):
            literal,display,_=source_number(table,row,column,token)
            actual=finite(float(match.group().replace(',','')))
            require(actual==display,'Semantic token differs from exact display')
            derived.append(dict(field=f'{row}:{column}:{token}',route=result['route'],status='reconciled',
                scope='numeric token of exact recomputed profile-support display',derived_from=result['field'],
                actual=actual,display=literal,absolute_delta=0.,functional_tolerance=0.,
                exact_display_match=True))
    expression=mapped.get('expression',{})
    raw=re.split(r'\\\\',table['source_rows'][row].split('&')[column])[0].strip()
    if expression.get('op')=='wins' and re.fullmatch(r'\d+\s*/\s*\d+',raw):
        contrasts=expression.get('contrasts',[])
        case_ids=[];operand_rows=[]
        def rows(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in ('row','d_row','w_row','train_row'):
                        require(isinstance(item,str) and len(item.split('/'))==4,'Win operand row identity is incomplete')
                        yield item
                    else:yield from rows(item)
            elif isinstance(value,list):
                for item in value:yield from rows(item)
        for contrast in contrasts:
            members=sorted(set(rows(contrast)));cases={item.split('/')[1] for item in members}
            require(len(cases)==1,'Win contrast needs one actually evaluated case identity')
            case_ids.append(next(iter(cases)));operand_rows.append(members)
        require(len(set(case_ids))==len(case_ids),'Win denominator repeats a case identity')
        require(contrasts and len({json.dumps(x,sort_keys=True) for x in contrasts})==len(contrasts),
                'Win roster is empty or duplicates a contrast')
        literal,display,_=source_number(table,row,column,1)
        status=result['status']
        if status=='reconciled':status='contract_checked' if display==len(contrasts) else 'failed'
        derived.append(dict(field=f'{row}:{column}:1',route=result['route'],status=status,
            scope='cardinality of distinct actually reconciled win contrasts; metadata, not a score',
            derived_from=result['field'],actual=len(case_ids),display=literal,
            distinct_case_ids=case_ids,actual_operand_rows=operand_rows))
    return derived


def case_bindings(kind):
    """Frozen semantic pointer -> source field; excludes unprinted median eta."""
    bindings = []; contracts = []
    if kind == 'initial_mark':
        table = '09_temporal_mark_extensions:table:1'
        for i in range(6):
            row = i+2
            for suffix,col in [('selected',2),('median_glr',6),('wilson95_among_resolved/0',4),('wilson95_among_resolved/1',5)]:
                bindings.append((table,'tab:pilot-frequency',f'/groups/{i}/{suffix}',row,col,0))
            contracts += [(table,row,1,0,[0.,.5,.9][i%3],'fixed persistence law'),
                          (table,row,2,1,20,'planned paired forests'),(table,row,3,0,0,'complete retained case roster')]
        table = '09_temporal_mark_extensions:table:2'
        for i in range(4):
            for typ,start in [('selection',2),('glr',5)]:
                for suffix,col in [('mean',start),('percentile95/0',start+1),('percentile95/1',start+2)]:
                    bindings.append((table,'tab:pilot-paired',f'/paired_contrasts/{i}/paired_{typ}_difference/{suffix}',i+2,col,0))
            contracts.append((table,i+2,1,0,[.5,.9][i%2],'fixed persistence law'))
    elif kind == 's02':
        table = '09_s02_completed:table:1'
        for i in range(6):
            for suffix,col,token in [('selected',2,0),('wilson95/0',3,0),('wilson95/1',3,1),('empirical_h0_95threshold',4,0),('above_empirical_threshold',5,0)]:
                bindings.append((table,'tab:s02-completed',f'/table/{i}/{suffix}',i+1,col,token))
            contracts += [(table,i+1,1,0,[0.,.5,.9][i%3],'fixed persistence law'),
                          (table,i+1,2,1,100,'planned paired forests'),(table,i+1,5,1,100,'planned paired forests')]
        table = '09_s02_completed:table:2'
        for row,i in enumerate((1,2,4,5),1):
            for suffix,col in [('mean',2),('median',3),('mcse',4)]:
                bindings.append((table,'tab:s02-paired',f'/paired_glr_differences/{i}/{suffix}',row,col,0))
            contracts.append((table,row,1,0,[.5,.9][(row-1)%2],'fixed persistence law'))
        table = '09_s02_completed:table:3'
        for i in range(3):
            for suffix,col in [('mean',1),('mcse',2)]:
                bindings.append((table,'unnumbered_label:within_forest_M2minusM1',f'/cross_procedure/{i}/glr/{suffix}',i+1,col,0))
            contracts.append((table,i+1,0,0,[0.,.5,.9][i],'fixed persistence law'))
    else: raise ValueError('Unknown case route')
    return bindings,contracts


def add_case_route(kind, delta, execution, protocol, inventory, observations, required, route, checked_cases=None):
    require(execution.get('passed') is True and execution.get('full_complete') is True
            and execution.get('mode') == 'completion', 'Case table delta needs actual complete output')
    require(len(set(protocol['roster']))==len(protocol['roster']),'Duplicate protocol case identity')
    require([x['case_id'] for x in execution['cases']] and
            len(execution['cases']) == len(protocol['roster']) and
            {x['case_id'] for x in execution['cases']} == set(protocol['roster']), 'Incomplete/duplicate case roster')
    for entry in execution['cases']:
        require(entry.get('passed',True) is True,'An indexed case explicitly failed')
        record=checked_cases.get(entry['case_id'],{}) if checked_cases is not None else entry
        require(record.get('passed') is True and record.get('case_id')==entry['case_id'],
                'Individual passed case evidence is required')
    wanted = 60 if kind == 'initial_mark' else 300
    require(len(protocol['roster']) == wanted, 'Case contract size changed')
    hvalues=[]
    for identity in protocol['roster']:
        match=re.search(r'_h(\d+)p(\d+)$',identity)
        require(match is not None,'Case persistence identity is absent')
        hvalues.append(float(match[1]+'.'+match[2]))
    require(Counter(hvalues)=={0.:wanted//3,.5:wanted//3,.9:wanted//3},'Case persistence roster changed')
    lookup = {(c['table'],c['pointer']):c for c in delta['cells']}
    require(len(lookup) == len(delta['cells']), 'Duplicate case table pointer')
    require(delta['manuscript_sources'] == protocol['table_links'], 'Case manuscript source crosswalk changed')
    bindings, contracts = case_bindings(kind)
    # Pointer indices follow the frozen summary's method/persistence order.
    # Check the visible method labels as well as the numerical field positions.
    table_starts = ([('09_temporal_mark_extensions:table:1',2,6),('09_temporal_mark_extensions:table:2',2,4)]
                    if kind=='initial_mark' else [('09_s02_completed:table:1',1,6),('09_s02_completed:table:2',1,4)])
    for tid,start,count in table_starts:
        for i in range(count):
            expected = ('Supplied' if i<count//2 else 'Fitted (primary)') if kind=='initial_mark' else ('M1' if i<count//2 else 'M2')
            require(inventory[tid]['source_rows'][start+i].split('&')[0].strip()==expected,'Case method-row ordering changed')
    for table_id,label,ptr,row,col,token in bindings:
        table = inventory[table_id]
        if not label.startswith('unnumbered_label:'):
            require(label in table['labels'], 'Case label/source mismatch')
            source_links=[x for x in protocol['table_links'] if x.get('label')==label]
        else:
            require(any('Within-forest M2 minus M1 GLR contrasts' in c for c in table['caption']), 'Case unnumbered caption mismatch')
            source_links=[x for x in protocol['table_links'] if x.get('caption')=='Within-forest M2 minus M1 GLR contrasts']
        require(len(source_links)==1 and source_links[0]['source']==table['source_file'],'Case protocol/manuscript source differs')
        literal,display,half=source_number(table,row,col,token)
        key=f'{row}:{col}:{token}';required[table_id].add(key)
        cell=lookup.get((label,ptr))
        result=dict(field=key,route=route,source_pointer=ptr,status='not_run',scope='recomputed case summary',display=literal)
        if cell:
            actual=finite(cell['recomputed']);tol=finite(cell['tolerance']);require(tol>=0,'Negative case tolerance')
            diff=abs(actual-display)
            result.update(actual=actual,absolute_delta=diff,functional_tolerance=tol,rounding_half_unit=half,
                allowed_absolute_delta=tol+half,exact_display_match=diff<=half and cell.get('displayed_rounding_matches') is not False,
                status='reconciled' if cell.get('passed') is True and diff<=tol+half else 'failed',
                producer_display_rounding_matches=cell.get('displayed_rounding_matches'))
        observations[table_id].setdefault(key,[]).append(result)
    for table_id,row,col,token,value,scope in contracts:
        literal,display,_=source_number(inventory[table_id],row,col,token)
        key=f'{row}:{col}:{token}';required[table_id].add(key)
        observations[table_id].setdefault(key,[]).append(dict(field=key,route=route,
            status='contract_checked' if display==value else 'failed',display=literal,actual=value,
            scope=scope+'; metadata only, not likelihood replay'))


def json_pointer(value, pointer):
    require(isinstance(pointer,str) and (pointer=='' or pointer.startswith('/')),'Invalid metadata pointer')
    for part in pointer.split('/')[1:]:
        name=part.replace('~1','/').replace('~0','~')
        require(not any(x in ('expected','reference','original_gain') or x.startswith(('expected_','reference_'))
                        for x in name.split('/')),'Expected/reference metadata operand is forbidden')
        value=value[int(name)] if isinstance(value,list) else value[name]
    return value


def add_metadata_dispositions(resources, spec, inventory, observations, required):
    """Explicit checked identities/counts, never implicit numeric exemptions.

The resource has schema score_table_metadata_dispositions_v1 and entries with
current table_id/source_body_sha256/source_row_index/column_index/token index,
source_token, role and evidence. Evidence pins a JSON resource, record_pointer,
identity_pointer/identity and value_pointer. The resolved record itself must
have passed=true. Values are primitive numeric metadata derived in that retained
record; this layer verifies its identity and exact display, not its derivation.
"""
    document=resources.json(spec,'metadata_dispositions')
    require(document.get('schema')=='score_table_metadata_dispositions_v1','Unknown metadata disposition schema')
    seen=set()
    for i,entry in enumerate(document['entries']):
        tid=entry['table_id'];require(tid in inventory,'Metadata table identity unknown')
        table=inventory[tid]
        require(entry['source_body_sha256']==table['body_sha256'],'Metadata source identity differs')
        role=entry['role']
        require(role in ('fold_id','seed','year','interval_endpoint','count','contrast_arm_label'),
                'Metadata disposition cannot excuse a scientific score')
        row=entry['source_row_index'];column=entry['column_index'];token=entry['numeric_token_index']
        field=f'{row}:{column}:{token}'
        require((tid,field) not in seen,'Duplicate metadata disposition');seen.add((tid,field))
        require(field in inventory_numeric_fields(table),'Metadata must identify a literal numeric source field')
        literal,display,_=source_number(table,row,column,token)
        require(literal==entry['source_token'],'Metadata source token differs')
        evidence=entry['evidence'];doc=resources.json(evidence['resource'],f'metadata/{i}')
        record=json_pointer(doc,evidence['record_pointer'])
        require(isinstance(record,dict) and record.get('passed') is True,'Metadata evidence record did not pass')
        require(json_pointer(record,evidence['identity_pointer'])==evidence['identity'],'Metadata evidence identity differs')
        actual=finite(json_pointer(record,evidence['value_pointer']))
        required[tid].add(field)
        observations[tid].setdefault(field,[]).append(dict(field=field,route='explicit_metadata',
            status='metadata_checked' if actual==display else 'failed',display=literal,actual=actual,
            role=role,scope='exact retained identity/count metadata; not a freshly replayed score',
            evidence=entry['evidence']))


def merge_fields(requirements, observations):
    result=[]
    for field in sorted(requirements):
        evidence=observations.get(field,[])
        failed=[x for x in evidence if x['status']=='failed']
        passed=[x for x in evidence if x['status'] in ('reconciled','contract_checked','metadata_checked')]
        status='failed' if failed else ('reconciled' if any(x['status']=='reconciled' for x in passed) else 'metadata_checked' if any(x['status']=='metadata_checked' for x in passed) else 'contract_checked') if passed else 'not_run'
        result.append(dict(field=field,status=status,evidence=evidence,
            gap=None if passed or failed else 'No successful actual table-cell mapping; route completion alone is insufficient'))
    return result


def build(repo, manifest_path, output):
    require(not output.exists(),'Coverage output must be new')
    manifest_raw=manifest_path.read_bytes();manifest=json.loads(manifest_raw)
    require(manifest.get('schema')=='score_table_coverage_inputs_v1','Unknown coverage manifest')
    resources=Resources(repo,manifest_path)
    plan=resources.json(manifest['plan'],'plan');inventory_raw=resources.json(manifest['inventory'],'inventory')
    inventory={x['id']:x for x in inventory_raw['tables']};dependencies={x['table_id']:x for x in plan['table_dependencies']}
    require(len(inventory)==len(inventory_raw['tables'])==plan['table_count'] and set(inventory)==set(dependencies),'Table census differs')
    current={}
    for identity,table in inventory.items():
        rel=table['source_file']
        require(identity.rsplit(':table:',1)[0]==Path(rel).stem,'Table identifier/source filename differs')
        if rel not in current:current[rel]=parse_tables(portable(repo,rel).read_bytes().decode('utf-8'))
        item=current[rel][int(identity.rsplit(':',1)[1])-1]
        require(item['body_sha256']==table['body_sha256'] and dependencies[identity]['source_file']==rel,'Current source/table body changed: '+identity)
        require(item['source_rows']==table['source_rows'],'Current table rows changed')
    required={k:inventory_numeric_fields(table) for k,table in inventory.items()}
    observations={k:{} for k in inventory};route_records=[]
    route_ids=set()
    for route in manifest.get('routes',[]):
        rid=route['id'];kind=route['kind'];require(rid not in route_ids,'Duplicate route identity');route_ids.add(rid)
        delta=resources.json(route['delta'],rid+'/delta');producer_raw=resources.raw(route['producer'],rid+'/producer')
        if 'review' in route:resources.json(route['review'],rid+'/attributed_review')
        route_records.append(dict(id=rid,kind=kind,delta_sha256=route['delta']['sha256'],producer_sha256=digest(producer_raw),scope=delta.get('scope')))
        if kind in ('cached','regional'):
            links=resources.json(route['links'],rid+'/links');resources.json(route['evidence'],rid+'/evidence')
            require(delta['links_sha256']==route['links']['sha256'],'Delta mapping identity')
            key='evidence_index_sha256' if kind=='cached' else 'evidence_manifest_sha256'
            require(delta[key]==route['evidence']['sha256'],'Delta evidence identity')
            if kind=='regional':require(delta['reconciler_sha256']==digest(producer_raw),'Regional producer identity')
            if delta.get('additional_evidence_sha256'):
                resources.json(route['additional'],rid+'/additional')
                require(delta['additional_evidence_sha256']==route['additional']['sha256'],'Additional cached evidence identity')
            reports={t.get('id',t.get('table_id')):t for t in delta['tables']}
            require(len(reports)==len(delta['tables']),'Duplicate delta table')
            for table in links['tables']:
                tid=table['id'];require(tid in inventory,'Unknown mapped table')
                require(table['source_file']==inventory[tid]['source_file'] and
                        table.get('source_body_sha256',table.get('body_sha256'))==inventory[tid]['body_sha256'],'Mapping source identity')
                report=reports.get(tid,{});cells={field_key(c):c for c in report.get('cells',[])}
                require(len(cells)==len(report.get('cells',[])),'Duplicate delta cell')
                for cell in table['cells']:
                    field=field_key(cell);required[tid].add(field)
                    result=checked_cell(inventory[tid],cell,cells.get(field),rid,kind)
                    observations[tid].setdefault(field,[]).append(result)
                    for companion in companion_fields(inventory[tid],cell,result):
                        required[tid].add(companion['field'])
                        observations[tid].setdefault(companion['field'],[]).append(companion)
        elif kind in ('initial_mark','s02'):
            execution=resources.json(route['execution'],rid+'/execution');protocol=resources.json(route['protocol'],rid+'/protocol')
            require(execution['table_deltas_sha256']==route['delta']['sha256'] and execution['protocol_sha256']==route['protocol']['sha256'],'Case result/delta/protocol identity')
            producer_path=route['producer']['path']
            require(execution['source_sha256'].get(producer_path)==digest(producer_raw),'Case producer identity')
            checked=case_records(resources,route['execution'],execution,rid+'/case')
            add_case_route(kind,delta,execution,protocol,inventory,observations,required,rid,checked)
        else:raise ValueError('Unknown reconciliation route')
    if 'metadata_dispositions' in manifest:
        add_metadata_dispositions(resources,manifest['metadata_dispositions'],inventory,observations,required)
    prior_specs=manifest.get('prior_evidence',{});prior_checked={}
    for name,spec in prior_specs.items():
        parts=name.split('#',1)
        require(spec.get('base','repository')=='repository' and
                (spec.get('path')==parts[0] if len(parts)==1 else
                 spec.get('archive')==parts[0] and spec.get('member')==parts[1]),'Prior evidence identity was substituted')
        prior=resources.json(spec,'prior/'+name)
        require((isinstance(prior,dict) and prior.get('passed') is True)
                or (name.endswith('s04b_completed_scores_20261105.json') and isinstance(prior,list) and len(prior)==20),
                'Prior evidence is not a passed retained report or its declared score rows')
        prior_checked[name]=spec['sha256']
    reports=[]
    for tid,table in inventory.items():
        dep=dependencies[tid];fields=merge_fields(required[tid],observations[tid]);state=dep['execution_status']
        missing_prior=[name for name in dep['prior_evidence'] if name not in prior_checked]
        if any(c['status']=='failed' for c in fields):status='failed'
        elif state=='no_likelihood_evaluation_required':status='no_likelihood_required'
        elif state=='already_replayed':status='prior_replay_retained' if dep['prior_evidence'] and not missing_prior else 'not_run'
        elif not fields:status='unmapped'
        elif any(c['status']=='not_run' for c in fields):status='partial' if any(c['status']!='not_run' for c in fields) else 'not_run'
        else:status='mapped_fields_reconciled'
        numeric=[x for c in fields for x in c['evidence'] if 'absolute_delta' in x]
        reports.append(dict(table_id=tid,source_file=table['source_file'],body_sha256=table['body_sha256'],labels=table['labels'],
            status=status,scope=dep['coverage_limit'],study_routes=dep['study_routes'],field_count=len(fields),
            field_status_counts=dict(Counter(c['status'] for c in fields)),maximum_absolute_delta=max((x['absolute_delta'] for x in numeric),default=None),
            maximum_functional_tolerance=max((x['functional_tolerance'] for x in numeric),default=None),
            display_rounding_differences=[c['field'] for c in fields if any(x.get('exact_display_match') is False for x in c['evidence'])],
            prior_evidence=[dict(identity=n,sha256=prior_checked.get(n)) for n in dep['prior_evidence']],missing_prior_evidence=missing_prior,
            fields=fields,gap=('No executable table-cell mapping supplied' if status=='unmapped' else
                'One or more source numeric fields lack successful mapped score or explicit metadata evidence' if status in ('partial','not_run') else None)))
    accepted={'mapped_fields_reconciled','prior_replay_retained','no_likelihood_required'}
    complete=all(t['status'] in accepted for t in reports)
    result=dict(schema='terminal_score_table_coverage_v1',passed=complete,census_verified=True,table_count=len(reports),
        status_counts=dict(Counter(t['status'] for t in reports)),manifest_sha256=digest(manifest_raw),producer_sha256=digest(Path(__file__).read_bytes()),
        resources=resources.used,routes=route_records,tables=reports,previously_withdrawn=plan['previously_withdrawn'],
        missing_tables=[t['table_id'] for t in reports if t['status'] not in accepted],
        scope='Every literal numeric source data field requires exact mapped score or explicit metadata evidence, alongside separately labelled pinned prior and non-likelihood scopes. No route-to-table promotion, model evaluation, fit, generation or independent scientific acceptance. Display rounding differences remain explicit.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',type=Path,default=ROOT);parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=build(args.repository.resolve(),args.evidence.resolve(),args.output.resolve())
    print(json.dumps({k:result[k] for k in ('passed','table_count','status_counts','missing_tables')}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
