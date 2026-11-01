"""Verify a typed portable ledger. Default is read-only; no scientific execution.
After source freeze use --write-receipts. --authority-only is not release-ready.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import argparse, copy, hashlib, json, math, re

ROOT = Path(__file__).resolve().parents[1]
NUMBER_BODY = r"(?:\d{1,3}(?:(?:,|\{,\})\d{3})+|\d+)(?:\.\d+)?|\.\d+"
NUMBER = re.compile(r"[+-]?(?:"+NUMBER_BODY+r")(?:[eE][+-]?\d+)?")
LOCATOR = re.compile(r"^line ([1-9]\d*), columns ([1-9]\d*)-([1-9]\d*): (.*)$")
IDENTITY_TRANSFORMS = {
 'identity','identity; audit display uses full parsed scalar','decimal rounding to displayed precision',
 'identity/rounding','rounding to 6 significant digits','decimal rounding to retained source display',
 'identity via protected-results named semantic mapping','round directly to six decimal places from original upstream value',
 'identity/rounding directly from authoritative scalar','rounding to displayed precision'}
DOC_TRANSFORMS = {
 'identity of displayed source text; source rounding retained','identity: retained source display',
 'identity of retained source text','identity of exact displayed source text; source precision retained, singleton JSON scalar unresolved',
 'identity of complete documentary numeric token'}
ROLES = {'manuscript_binding','source_inventory_only','source_inventory_not_literal_final_display'}

@dataclass(frozen=True)
class Token:
 start: int
 end: int
 text: str
 kind: str

def digest(data): return hashlib.sha256(data).hexdigest()

def strict_json(raw):
 def pairs(items):
  result={}
  for key,value in items:
   if key in result: raise ValueError('duplicate_json_key:'+key)
   result[key]=value
  return result
 return json.loads(raw,object_pairs_hook=pairs)

def numeric_value(value):
 if isinstance(value,bool) or value is None: raise ValueError('not_a_numeric_scalar')
 s=str(value).strip().replace('−','-').replace(r'\,','')
 if not NUMBER.fullmatch(s): raise ValueError('invalid_complete_numeric_representation')
 try: d=Decimal(s.replace('{,}','').replace(',',''))
 except InvalidOperation as exc: raise ValueError('invalid_numeric_representation') from exc
 if not d.is_finite(): raise ValueError('nonfinite_numeric_value')
 return d

def equal_display(raw,claim):
 desired,actual=numeric_value(claim['display']),numeric_value(raw)
 precision=Decimal(10)**desired.as_tuple().exponent
 slack=max(abs(actual),abs(desired))*Decimal('2e-14')+Decimal('1e-28')
 return abs(actual-desired)<=precision/2+slack

@lru_cache(maxsize=8192)
def tokens(line):
 """Full scalar literals, with non-scalar documentary syntax classified first.
 Formula fragments are retained as text, never assigned inferred scalar meaning.
 """
 result=[]
 def add(a,b,kind):
  if a<b and not any(a<t.end and b>t.start for t in result): result.append(Token(a,b,line[a:b],kind))
 def mark(pattern,kind,flags=0,predicate=None):
  for m in re.finditer(pattern,line,flags):
   if predicate is None or predicate(m): add(m.start(),m.end(),kind)
 if re.match(r'^\s*\\(?:documentclass|usepackage|geometry|setlength|renewcommand|newcommand|hypersetup|pagestyle)\b',line): add(0,len(line),'typesetting_metadata')
 if re.match(r'^\s*#{1,6}\s',line): add(0,len(line),'section_heading')
 if re.match(r'^\s*\\begin\{(?:longtable|tabular|tabularx)\}',line): add(0,len(line),'typesetting_metadata')
 mark(r'\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}','typesetting_metadata')
 mark(r'\\cite\w*\*?(?:\[[^\]]*\])*\{[^}]*\}','citation')
 mark(r'\\(?:label|ref|eqref|cref|Cref|bibitem|bibentry)\{[^}]*\}','reference_identifier')
 mark(r'\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:?\d{2}:?\d{2}(?:\.\d+)?Z?)?\b','date')
 mark(r'\b\d{8}T\d{6}Z\b','timestamp_identifier')
 mark(r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b','date')
 mark(r'\b(?:19|20)\d{2}\s*(?:--|[-–])\s*(?:19|20)\d{2}\b','calendar_range')
 mark(r'(?<![\d.])\d+(?:\.\d+){2,}(?!\d|\.\d)','software_version')
 mark(r'\b(?:Python|NumPy|SciPy|Matplotlib|Tectonic|GNU Octave|Octave|DeepSeek|Claude Opus|Gemini|GPT)\s+\d+(?:\.\d+)+','software_version')
 mark(r'(?<![A-Za-z0-9.])[0-9a-fA-F]{16,}(?![A-Za-z0-9])','hash',predicate=lambda m:bool(re.search('[a-fA-F]',m[0])) and not NUMBER.fullmatch(m[0]))
 mark(r'\b\d{4}[a-z]\d+\b','catalogue_identifier')
 mark(r'`[^`]+`','path_or_identifier',predicate=lambda m:bool(re.search(r'[/\\]|\.(?:json|md|tex|pdf|png|csv|py|dll|exe)\b|\d{8}T',m[0])))
 mark(r'\bSHA[- ]?256\b','hash_algorithm',re.I)
 mark(r'\[(?:19|20)\d{2},\s*(?:19|20)\d{2}[)\]]','calendar_interval')
 mark(r'\\(?:tfrac|frac|dfrac)(?:\{[^{}]*\}|\d){2}','mathematical_expression')
 mark(r'(?:\d+(?:\.\d+)?\\times\s*)?10\^\{[+-]?\d+\}','mathematical_expression')
 mark(r'(?<![\d.])\d+(?:\.\d+)?\s*(?:--|[-–])\s*\d+(?:\.\d+)?(?!\d|\.\d|[eE][+-]?\d)','range_or_difference_expression')
 mark(r'(?:\\[A-Za-z]+|(?<![A-Za-z0-9])[A-Za-z](?:_\{?\w+\}?)?)[+-]\d+(?:\.\d+)?','mathematical_expression')
 mark(r'\b(?:order|type|post|pre|calendar)[-–]\d+\b','qualified_identifier',re.I)
 mark(r'\b(?:19|20)\d{2}-origin\b','calendar_identifier')
 mark(r'\b(?:Thread|Fold|Main)\d+(?:/\d+)+','identifier',re.I)
 mark(r'\b(?:Section|Table|Figure|Appendix|Equation|Theorem|Corollary|Proposition|Lemma|Definition|Eq\.)\s+\d+(?:\.\d+)*','reference_identifier',re.I)
 mark(r'[A-Za-z]_\{\d+\}','mathematical_identifier')
 def identifier(m):
  return not (re.match(r'(?i)(?:(?:same|and|or|around|order)\d|M\d)',m[0]) or (m.start()>0 and line[m.start()-1]=='\\') or (re.search(r'\d[eE]$',m[0]) and re.match(r'[+-]?\d',line[m.end():])))
 mark(r'(?<![A-Za-z0-9_])[A-Za-z_]+\d+[A-Za-z0-9_]*','identifier',predicate=identifier)
 mark(r'[+-]?\d+(?:\.\d+)?(?:,\s*[+-]?\d+(?:\.\d+)?)+','numeric_sequence',predicate=lambda m:not NUMBER.fullmatch(m[0]))
 for m in NUMBER.finditer(line.replace('−','-')): add(m.start(),m.end(),'numeric')
 return sorted(result,key=lambda t:(t.start,t.end))

def select_token(line,start,end):
 candidates=[t for t in tokens(line) if t.start<end and t.end>start]
 if len(candidates)!=1: raise ValueError('ambiguous_or_missing_documentary_token')
 return candidates[0]

def parse_locator(record,text):
 m=LOCATOR.fullmatch(record.get('source_locator',''))
 if not m: raise ValueError('malformed_documentary_locator')
 lines=text.splitlines(); n,a,b=int(m[1]),int(m[2])-1,int(m[3])
 if n>len(lines) or b<=a or b>len(lines[n-1]): raise ValueError('documentary_columns_out_of_range')
 line=lines[n-1]
 if m[4]!=line: raise ValueError('documentary_locator_context_mismatch')
 return line,a,b

def resolve(data,pointer):
 if not isinstance(pointer,str) or (pointer and not pointer.startswith('/')): raise ValueError('invalid_json_pointer')
 if pointer=='': return data
 for part in pointer[1:].split('/'):
  if re.search(r'~(?![01])',part): raise ValueError('invalid_json_pointer_escape')
  key=part.replace('~1','/').replace('~0','~')
  if isinstance(data,list):
   if not re.fullmatch(r'0|[1-9]\d*',key): raise ValueError('invalid_array_pointer_index')
   data=data[int(key)]
  elif isinstance(data,dict): data=data[key]
  else: raise ValueError('json_pointer_crosses_scalar')
 return data

def transformed(value,c,data):
 def number(x):
  if type(x) not in {int,float,Decimal}: raise ValueError('arithmetic_operand_must_be_numeric_not_boolean')
  numeric_value(x)
  return x
 tr=c.get('transformation')
 if isinstance(tr,dict):
  op=tr.get('operation'); operands=[resolve(data,p) for p in tr.get('operand_pointers',[])]
  if 'operand_pointer' in tr and tr['operand_pointer']!=c['json_pointer']: raise ValueError('transform_operand_mismatch')
  if 'operand_values' in tr and tr['operand_values']!=operands: raise ValueError('stale_transform_operand_values')
  for p in tr.get('eligibility_pointers',[]):
   if resolve(data,p) is not True: raise ValueError('derived_operand_eligibility_failed')
  if op=='length': return len(resolve(data,tr['operand']))
  if op in {'identity','identity then displayed rounding'}: return value
  if op in {'negate','negate then displayed rounding'}: return -number(value)
  if op in {'divide','divide_then_round'}: return number(value)/number(tr['divisor'])
  if op in {'multiply','multiply_then_round'}: return number(value)*number(tr.get('factor',tr.get('multiplier')))
  if op=='microseconds_to_days then displayed rounding': return number(value)/86400000000
  if op in {'difference','difference then displayed rounding'}: return number(operands[0])-number(operands[1])
  if op in {'ratio','ratio then displayed rounding'}: return number(operands[0])/number(operands[1])
  if op=='percent_ratio then displayed rounding': return 100*number(operands[0])/number(operands[1])
  if op=='sum': return sum(number(x) for x in operands)/number(tr.get('divisor',1))
  if op=='ceil': return math.ceil(number(value)/number(tr['quantum']))*tr['quantum']
  if op=='saved_background_ratio_at_origin':
   if resolve(data,'/rows/0/fold')!='fold_50': raise ValueError('horizon_half_origin_binding_failed')
   ai,ae,di,de,t,half_horizon=[number(x) for x in operands]; return math.exp(ai-ae+(di-de)*(t/half_horizon-1))
  if op in {'count_named_status','count_expected_zero'}:
   expected=tr['status'] if op=='count_named_status' else 0
   if op=='count_expected_zero': operands=[number(x) for x in operands]
   if any(x!=expected for x in operands): raise ValueError('count_operand_mismatch')
   return len(operands)
  if op in {'round','round directly from upstream scalar after named unit/sign transform'}:
   prior=tr.get('prior_binding_transformation')
   if prior:
    if isinstance(prior,str):
     if prior not in IDENTITY_TRANSFORMS: raise ValueError('unsupported_prior_transform')
     return value
    if prior.get('operand_pointer')!=c['json_pointer']: raise ValueError('transform_operand_mismatch')
    if prior.get('operation')=='divide': return number(value)/number(prior['divisor'])
    if prior.get('operation')=='negate': return -number(value)
    raise ValueError('unsupported_prior_transform')
   return value
  raise ValueError('unsupported_transformation:'+str(op))
 if tr in IDENTITY_TRANSFORMS: return value
 if tr=='negate negative contrast to report loss magnitude, then round': return -number(value)
 if tr=='percent_round_2': return 100*number(value)
 if tr=='bytes_to_GiB': return number(value)/1024**3
 if tr=='array_cardinality': return len(value)
 if tr=='sum_method_status_counts':
  if not isinstance(value,dict) or not all(type(v) is int and v>=0 for v in value.values()): raise ValueError('invalid_method_status_counts')
  return sum(value.values())
 if tr=='count_null_reference_statistic16_exact_zero':
  eligible=[(i,x) for i,x in enumerate(value) if x.get('role')=='null_reference']
  if type(c['denominator']) is not int or len(eligible)!=c['denominator']: raise ValueError('reference_denominator_mismatch')
  exact=[c['json_pointer']+'/'+str(i)+'/statistic16' for i,x in eligible if number(x['statistic16'])==0.0]
  if set(exact)!=set(c['exact_zero_record_pointers']): raise ValueError('exact_zero_record_identity_mismatch')
  if any(resolve(data,p)!=c['denominator'] for p in c['supporting_json_pointers']): raise ValueError('reference_supporting_count_mismatch')
  return len(exact)
 raise ValueError('unsupported_transformation:'+str(tr))

def safe_path(root,relative):
 if not isinstance(relative,str) or not relative or Path(relative).is_absolute(): raise ValueError('package_relative_path_required')
 p=(root/relative).resolve()
 if not p.is_relative_to(root.resolve()): raise ValueError('path_escapes_package')
 return p

def safe_tex_path(root,relative):
 if not isinstance(relative,str) or not relative or Path(relative).is_absolute(): raise ValueError('manuscript_source_tex_path_required')
 base=(root/'paper/source').resolve(); p=(base/relative).resolve()
 if not p.is_relative_to(base) or p.suffix!='.tex': raise ValueError('manuscript_path_escapes_tex_source')
 return p

def manuscript_numbers(text):
 text=text.replace('−','-').replace(r'\,','')
 text=re.sub(r'\\shortstack(?:\[[^\]]*\])?\{\$([+-]?\d+(?:\.\d+)?)\$\\\\\$\\times10\^\{([+-]?\d+)\}\$\}',r'\1e\2',text)
 text=re.sub(r'([+-]?\d+(?:\.\d+)?)\s*\\times\s*10\^\{([+-]?\d+)\}',r'\1e\2',text)
 text=re.sub(r'(?<![\d.])10\^\{([+-]?\d+)\}',r'1e\1',text)
 values=set()
 for line in text.splitlines():
  for t in tokens(line):
   if t.kind=='numeric': values.add(numeric_value(t.text))
   elif t.kind=='numeric_sequence': values.update(numeric_value(m[0]) for m in NUMBER.finditer(t.text))
 return values

def count_over_total(value,claim,data):
 fmt=claim['display_format']
 if fmt.get('kind')!='count_over_total': raise ValueError('unsupported_display_format')
 denominator=resolve(data,fmt['denominator_pointer'])
 m=re.fullmatch(r'(0|[1-9]\d*)/([1-9]\d*)',str(claim['display']))
 if not m or type(value) is not int or type(denominator) is not int or not 0<=value<=denominator: raise ValueError('invalid_count_over_total')
 if (int(m[1]),int(m[2]))!=(value,denominator): raise ValueError('count_over_total_source_mismatch')

def verify(root=ROOT,*,authority_only=False,refresh_presence=False):
 root=Path(root).resolve(); path=root/'validation/MASTER_CLAIM_LEDGER.json'
 failures,display_checks,source_hashes=[],[],{}; counts,cache=Counter(),{}
 try:
  raw_ledger=path.read_bytes(); ledger=strict_json(raw_ledger.decode('utf-8-sig'))
  claims=ledger['claims']; metadata=ledger.get('documentary_metadata',[])
  if not isinstance(claims,list) or not claims: raise ValueError('empty_or_invalid_claims')
  if not isinstance(metadata,list): raise ValueError('invalid_documentary_metadata')
  ids=[x['id'] for x in claims+metadata]
  if any(not isinstance(i,str) or not i for i in ids): raise ValueError('invalid_claim_id')
  if len(ids)!=len(set(ids)): raise ValueError('duplicate_claim_id')
 except Exception as exc: return {'passed':False,'release_ready':False,'failures':[{'error':str(exc)}],'counts':{}},None,[]
 result=copy.deepcopy(ledger); tex_cache={}
 def source(c):
  p=safe_path(root,c['bundled_source'])
  if p not in cache:
   raw=p.read_bytes(); cache[p]={'sha':digest(raw),'text':raw.decode('utf-8-sig'),'json':strict_json(raw) if p.suffix=='.json' else None}
  src=cache[p]
  if c['source_sha256']!=src['sha']: raise ValueError('source_hash_mismatch')
  return src
 for is_metadata,collection in [(False,result['claims']),(True,result.get('documentary_metadata',[]))]:
  for c in collection:
   try:
    src=source(c)
    if is_metadata:
     line,a,b=parse_locator(c,src['text']); t=select_token(line,a,b)
     if (a,b)!=(t.start,t.end) or line[a:b]!=c['text']: raise ValueError('metadata_slice_mismatch')
     if t.kind=='numeric' or t.kind!=c['metadata_kind']: raise ValueError('invalid_metadata_classification')
     if 'value' in c or 'display' in c: raise ValueError('metadata_must_not_claim_numeric_value')
     counts['documentary_metadata_verified']+=1; c['reconciliation_status']='verified_documentary_metadata'; continue
    if c.get('ledger_role') not in ROLES: raise ValueError('invalid_ledger_role')
    if not isinstance(c.get('display'),(str,int,float,bool)): raise ValueError('missing_or_invalid_display')
    if 'json_pointer' in c:
     raw_value=resolve(src['json'],c['json_pointer'])
     if c.get('json_value_kind') not in {None,'numeric_scalar','numeric_string','nonnumeric'}: raise ValueError('unknown_json_value_kind')
     if 'resolved_source_value' in c and (type(c['resolved_source_value']) is not type(raw_value) or c['resolved_source_value']!=raw_value): raise ValueError('stale_resolved_source_value')
     value=transformed(raw_value,c,src['json'])
     if c.get('json_value_kind')=='numeric_scalar' and type(value) not in {int,float,Decimal}: raise ValueError('incorrect_json_value_kind')
     if c.get('json_value_kind')=='nonnumeric' and type(value) in {int,float,Decimal}: raise ValueError('incorrect_json_value_kind')
     if type(value) in {int,float,Decimal} and numeric_value(c.get('value'))!=numeric_value(value): raise ValueError('stale_numeric_value_metadata')
     if c.get('display_format'): count_over_total(value,c,src['json'])
     elif type(value) in {int,float,Decimal} or c.get('json_value_kind')=='numeric_string':
      if c.get('json_value_kind')=='numeric_string' and (not isinstance(value,str) or c.get('value')!=value): raise ValueError('invalid_numeric_string_binding')
      if not equal_display(value,c): raise ValueError('display_does_not_round_from_source')
      if not equal_display(c.get('value'),c): raise ValueError('stale_numeric_value_metadata')
     elif type(value) is not type(c.get('value')) or value!=c.get('value') or str(value)!=str(c['display']): raise ValueError('nonnumeric_binding_requires_exact_type_and_value')
     counts['json_numeric_verified' if type(value) in {int,float,Decimal} or c.get('json_value_kind')=='numeric_string' else 'json_nonnumeric_verified']+=1
     c['binding_kind']='exact_json_pointer'; counts['json_pointer_verified']+=1
    else:
     if c.get('transformation') not in DOC_TRANSFORMS: raise ValueError('unsupported_documentary_transform')
     line,a,b=parse_locator(c,src['text']); declared=str(c.get('source_display',c['display']))
     if line[a:b]!=declared: raise ValueError('documentary_slice_mismatch')
     t=select_token(line,a,b)
     if t.kind!='numeric': raise ValueError('nonnumeric_token_requires_metadata_classification')
     if (a,b)!=(t.start,t.end): raise ValueError('incomplete_signed_numeric_token')
     if not equal_display(declared,c): raise ValueError('documentary_display_rounding_mismatch')
     if numeric_value(c['value'])!=numeric_value(c['display']): raise ValueError('documentary_value_display_mismatch')
     c['binding_kind']='complete_documentary_numeric_token'; counts['documentary_numeric_verified']+=1
    c['reconciliation_status']='verified_at_declared_granularity'
    declared_files=c.get('final_display_locations') or ([c['tex_file']] if c.get('tex_file') else [])
    if c.get('ledger_role')=='manuscript_binding' and not declared_files: raise ValueError('missing_manuscript_location')
    paths=[safe_tex_path(root,f) for f in declared_files] if c.get('ledger_role')=='manuscript_binding' else []
    if any(not p.is_file() for p in paths): raise ValueError('missing_declared_tex_file')
    if c.get('ledger_role')=='manuscript_binding' and not authority_only:
     wanted=None if c.get('display_format') else numeric_value(c['display']); locations=[]
     for p in paths:
      if p not in tex_cache:
       raw=p.read_bytes(); body=raw.decode('utf-8-sig'); tex_cache[p]=(manuscript_numbers(body),body); source_hashes[p.relative_to(root).as_posix()]=digest(raw)
      present_here=(bool(re.search(r'(?<![\w.+/-])'+re.escape(str(c['display']))+r'(?![\w./])',tex_cache[p][1].replace('\u2212','-'))) if c.get('display_format') else wanted in tex_cache[p][0])
      if present_here: locations.append(p.relative_to(root).as_posix())
     present=bool(locations)
     check={'id':c['id'],'present':present,'display':c['display'],'source_files':[p.relative_to(root).as_posix() for p in paths],'matching_files':locations}
     display_checks.append(check)
     current_hashes={p.relative_to(root).as_posix():source_hashes[p.relative_to(root).as_posix()] for p in paths}
     old_presence=c.get('final_display_presence')
     if not refresh_presence:
      if not isinstance(old_presence,dict): raise ValueError('missing_persisted_source_binding')
      if old_presence.get('source_hashes')!=current_hashes: raise ValueError('stale_persisted_source_hashes')
      if any(old_presence.get(k)!=check[k] for k in ['id','present','display','source_files','matching_files']): raise ValueError('stale_persisted_display_metadata')
     c['final_display_presence']=dict(check,source_hashes={p.relative_to(root).as_posix():source_hashes[p.relative_to(root).as_posix()] for p in paths},method='Complete signed numeric literals; representation and source identity, not semantic completeness.')
     if not present: raise ValueError('declared_manuscript_display_absent')
    elif authority_only: c.pop('final_display_presence',None)
   except Exception as exc:
    c['reconciliation_status']='failed'; failures.append({'id':c.get('id'),'error':str(exc),'display':c.get('display'),'bundled_source':c.get('bundled_source')})
 counts.update(claims=len(result['claims']),documentary_metadata=len(result.get('documentary_metadata',[])),total_records=len(ids),distinct_authorities=len(cache))
 counts['literal_manuscript_display_records']=sum(x['present'] for x in display_checks)
 counts['missing_declared_manuscript_displays']=sum(not x['present'] for x in display_checks)
 receipt={'schema':'typed_claim_reconciliation_v2','scope':'Saved authority identity, explicit transformations, full documentary tokens and declared numeric representation; no scientific execution or exhaustive semantic review.','authority_only':authority_only,'passed':not failures,'release_ready':not failures and not authority_only,'counts':dict(counts),'failures':failures,'ledger_sha256':digest(raw_ledger),'verifier_sha256':digest(Path(__file__).read_bytes()),'source_hashes':source_hashes,'completeness_limit':'Only enumerated claims are checked. Typed metadata is excluded from numerical claims. Missing manuscript claims are never automatically demoted.'}
 return receipt,result,display_checks

def format_ledger(ledger):
 parts=['{']; keys=list(ledger.keys())
 for ki,k in enumerate(keys):
  v=ledger[k]; comma=',' if ki<len(keys)-1 else ''
  if isinstance(v,list):
   parts.append(f'  {json.dumps(k)}: [')
   for ri,row in enumerate(v):
    rcomma=',' if ri<len(v)-1 else ''
    parts.append('    '+json.dumps(row,ensure_ascii=False,separators=(',',':'))+rcomma)
   parts.append(f'  ]{comma}')
  else: parts.append(f'  {json.dumps(k)}: {json.dumps(v,ensure_ascii=False)}{comma}')
 parts.append('}\n'); return '\n'.join(parts).encode('utf-8')

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=ROOT)
 p.add_argument('--authority-only',action='store_true',help='Incomplete pre-freeze verification, not release-ready')
 p.add_argument('--write-receipts',action='store_true',help='After source freeze refresh ledger and ledger-specific receipts')
 args=p.parse_args(argv)
 if args.authority_only and args.write_receipts: p.error('authority-only cannot write final receipts')
 receipt,ledger,checks=verify(args.root,authority_only=args.authority_only,refresh_presence=args.write_receipts)
 if args.write_receipts and receipt['release_ready']:
  dest=args.root/'validation'
  if 'revision' in ledger: ledger['revision']['source_freeze_status']='verified_current_source'
  raw=format_ledger(ledger)
  (dest/'MASTER_CLAIM_LEDGER.json').write_bytes(raw); receipt['ledger_sha256']=digest(raw)
  payload=json.dumps(receipt,indent=2,ensure_ascii=False)+'\n'
  for name in ['numeric_reconciliation_receipt.json','portable_reconciliation_receipt.json']: (dest/name).write_text(payload,encoding='utf-8')
  (dest/'manuscript_display_regression.json').write_text(json.dumps({'schema':'complete_signed_literal_regression_v2','ledger_sha256':receipt['ledger_sha256'],'verifier_sha256':receipt['verifier_sha256'],'source_hashes':receipt['source_hashes'],'checks':checks,'passed':True,'scope':receipt['completeness_limit']},indent=2)+'\n',encoding='utf-8')
 print(json.dumps(receipt,indent=2,ensure_ascii=False)); return 0 if receipt['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
