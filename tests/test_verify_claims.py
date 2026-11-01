"""Adversarial source-custody tests; no scientific models or external inputs."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tested_verifier',PACKAGE/'scripts/verify_claims.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)

class Fixture(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='verifier_test_',dir=Path(__file__).parent)
  self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  (self.root/'validation/authorities').mkdir(parents=True)
  (self.root/'paper/source').mkdir(parents=True)
 def source(self,text,name='source.txt'):
  p=self.root/'validation/authorities'/name;p.write_text(text,encoding='utf-8')
  return p.relative_to(self.root).as_posix(),v.digest(p.read_bytes())
 def doc(self,line='x=0.65',display='0.65',columns=None):
  path,sha=self.source(line+'\n');a,b=columns or (line.index(display),line.index(display)+len(display))
  return {'id':'sample','bundled_source':path,'source_sha256':sha,'source_path':'historical/unavailable','display':display,'value':float(display.replace('{,}','').replace(',','')),'source_locator':f'line 1, columns {a+1}-{b}: {line}','transformation':'identity of complete documentary numeric token','ledger_role':'manuscript_binding','tex_file':'chapter.tex'}
 def field(self,value,display=None):
  path,sha=self.source(json.dumps({'value':value,'denominator':3}),'source.json')
  return {'id':'sample','bundled_source':path,'source_sha256':sha,'display':str(value) if display is None else display,'value':value,'json_pointer':'/value','transformation':'identity','ledger_role':'manuscript_binding','tex_file':'chapter.tex'}
 def install(self,claim,tex=None,metadata=None):
  claims=claim if isinstance(claim,list) else [claim]
  ledger={'claims':claims,'documentary_metadata':metadata or []}
  (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_text(json.dumps(ledger),encoding='utf-8')
  (self.root/'paper/source/chapter.tex').write_text(str(claims[0]['display']) if tex is None else tex,encoding='utf-8')
  return ledger
 def result(self,**kwargs):return v.verify(self.root,refresh_presence=True,**kwargs)[0]
 def assertFails(self,error=None):
  r=self.result();self.assertFalse(r['passed'],r)
  if error:self.assertTrue(any(error in x['error'] for x in r['failures']),r['failures'])

class Boundaries(Fixture):
 def test_complete_numeric_controls(self):
  for value in ['0.65','-16.99','612','1e-5','-.95','1{,}000','4,019,138']:
   with self.subTest(value=value):
    c=self.doc('value='+value,value);c['value']=float(v.numeric_value(value));self.install(c);self.assertTrue(self.result()['passed'])
 def test_all_demonstrated_truncations(self):
  for line,display in [('x=0.65','0.6'),('x=-16.99','16.99'),('same612 targets','12'),('x=0.456','6'),('tolerance=1e-5','5'),('tolerance=1e-5','1'),('x=0.95','95')]:
   with self.subTest(line=line,display=display):
    self.install(self.doc(line,display));self.assertFails('incomplete_signed_numeric_token')
 def test_columns_cannot_point_elsewhere_on_line(self):
  self.install(self.doc('x=999','999',(0,1)));self.assertFails('documentary_slice_mismatch')
 def test_unparsed_locator_rejected(self):
  c=self.doc();c['source_locator']='appendix whatever';self.install(c);self.assertFails('malformed_documentary_locator')
 def test_out_of_range_and_reversed_columns(self):
  for span in [(0,99),(3,2),(-1,1)]:
   with self.subTest(span=span):self.install(self.doc(columns=span));self.assertFails()
 def test_wrong_context_payload(self):
  c=self.doc();c['source_locator']=c['source_locator'].replace('x=0.65','x=0.66');self.install(c);self.assertFails('context_mismatch')
 def test_documentary_value_is_not_a_second_unchecked_number(self):
  c=self.doc();c['value']=0.6;self.install(c);self.assertFails('value_display_mismatch')
 def test_lexical_metadata_is_not_numeric(self):
  for line,display in [(r'\citep{Hawkes1971}','971'),('Python 3.13.4','3.13'),('1993-05-24','-05'),(r'\documentclass[11pt]{article}','1')]:
   with self.subTest(line=line):self.install(self.doc(line,display));self.assertFails('nonnumeric_token_requires_metadata_classification')
 def test_tex_macro_does_not_swallow_real_threshold(self):
  for line in [r'\approx0.216065',r'\leq0.95',r'\geq0.5']:
   ts=[t.text for t in v.tokens(line) if t.kind=='numeric'];self.assertEqual(len(ts),1)
 def test_glued_prose_scientific_notation(self):
  ts=[t.text for t in v.tokens('order1e-5 or1e-6, same612 targets and16/32 checks') if t.kind=='numeric']
  for expected in ['1e-5','1e-6','612','16','32']:self.assertIn(expected,ts)

class Structure(Fixture):
 def test_missing_ledger(self):self.assertFails()
 def test_empty_ledger(self):
  (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_text('{"claims":[]}');self.assertFails('empty_or_invalid_claims')
 def test_duplicate_ids(self):
  c=self.doc();self.install([c,copy.deepcopy(c)]);self.assertFails('duplicate_claim_id')
 def test_duplicate_json_keys(self):
  (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_text('{"claims":[],"claims":[]}');self.assertFails('duplicate_json_key')
 def test_missing_declared_tex(self):
  self.install(self.field(1));(self.root/'paper/source/chapter.tex').unlink();self.assertFails('missing_declared_tex_file')
 def test_missing_location(self):
  c=self.field(1);c.pop('tex_file');self.install(c);self.assertFails('missing_manuscript_location')
 def test_authority_hash_mismatch(self):
  c=self.field(1);c['source_sha256']='0'*64;self.install(c);self.assertFails('source_hash_mismatch')
 def test_paths_must_stay_inside_package(self):
  c=self.field(1);c['bundled_source']='../outside.json';self.install(c);self.assertFails('path_escapes_package')
 def test_manuscript_paths_must_stay_in_tex_source(self):
  (self.root/'validation/not_manuscript.json').write_text('{"x":1}\n',encoding='utf-8')
  (self.root/'paper/source/not_tex.json').write_text('{"x":1}\n',encoding='utf-8')
  for bad in ['../../validation/not_manuscript.json','../source/not_tex.json','not_tex.json']:
   with self.subTest(bad=bad):
    c=self.field(1);c['tex_file']=bad;self.install(c);self.assertFails('manuscript_path_escapes_tex_source')
 def test_inventory_is_not_declared_manuscript(self):
  c=self.field(1);c['ledger_role']='source_inventory_only';c['tex_file']='not_applicable_independent_audit';self.install(c);self.assertTrue(self.result()['passed'])
 def test_authority_only_never_release_ready(self):
  self.install(self.doc());r=self.result(authority_only=True);self.assertTrue(r['passed']);self.assertFalse(r['release_ready'])

class TransformAndType(Fixture):
 def test_boolean_arithmetic_and_zero_count_are_rejected(self):
  for tr,raw,display in [({'operation':'negate'},True,'-1'),({'operation':'count_expected_zero','operand_pointers':['/value']},False,'1'),({'operation':'multiply','factor':True},1,'1')]:
   with self.subTest(tr=tr):
    c=self.field(raw,display);c['transformation']=tr;c['value']=int(display);self.install(c);self.assertFails('arithmetic_operand_must_be_numeric_not_boolean')
 def test_stale_numeric_value_metadata(self):
  c=self.field(612);c['value']=12;self.install(c);self.assertFails('stale_numeric_value_metadata')
  c=self.field(12);c['value']=12.1;c['value_semantics']='transformed_authority_scalar';self.install(c);self.assertFails('stale_numeric_value_metadata')
  c=self.field(1,'1/3');c['display_format']={'kind':'count_over_total','denominator_pointer':'/denominator'};c['value']=2;self.install(c);self.assertFails('stale_numeric_value_metadata')
 def test_stale_resolved_source_value(self):
  c=self.field(612);c['resolved_source_value']=12;self.install(c);self.assertFails('stale_resolved_source_value')
 def test_numeric_string_requires_explicit_kind_and_exact_source_value(self):
  c=self.field('-2.8912444043750796','-2.891244');c['json_value_kind']='numeric_string';self.install(c);self.assertTrue(self.result()['passed'])
  c['value']='-2.891244';self.install(c);self.assertFails('invalid_numeric_string_binding')
 def test_stale_transform_operand_values(self):
  c=self.field(612);c['transformation']={'operation':'identity','operand_pointers':['/value'],'operand_values':[12]};self.install(c);self.assertFails('stale_transform_operand_values')
 def test_wrong_sign_and_wrong_count_json(self):
  for raw,shown in [(-16.99,'16.99'),(612,'12')]:
   with self.subTest(raw=raw):self.install(self.field(raw,shown));self.assertFails('display_does_not_round')
 def test_unknown_string_transform(self):
  c=self.field(42);c['transformation']='divide by one thousand';self.install(c);self.assertFails('unsupported_transformation')
 def test_unknown_dict_transform_and_prior_transform(self):
  for tr in [{'operation':'magic'},{'operation':'round','prior_binding_transformation':'magic'}]:
   with self.subTest(tr=tr):c=self.field(42);c['transformation']=tr;self.install(c);self.assertFails('unsupported_')
 def test_declared_prior_identity_is_supported(self):
  c=self.field(1.828190,'1.82819');c['transformation']={'operation':'round','prior_binding_transformation':'rounding to displayed precision'};self.install(c);self.assertTrue(self.result()['passed'])
 def test_boolean_cannot_equal_numeric_zero(self):
  c=self.field(False,'0');c['value']=0;c['ledger_role']='source_inventory_only';self.install(c);self.assertFails('exact_type_and_value')
 def test_exact_boolean_inventory(self):
  c=self.field(True);c['ledger_role']='source_inventory_only';self.install(c);self.assertTrue(self.result()['passed'])
 def test_nonfinite_numeric_rejected(self):
  self.install(self.field(float('inf'),'Infinity'));self.assertFails('invalid_complete_numeric')
 def test_count_denominator_has_an_authority_pointer(self):
  c=self.field(1,'1/3');c['display_format']={'kind':'count_over_total','denominator_pointer':'/denominator'};self.install(c);self.assertTrue(self.result()['passed'])
  c['display']='1/2';self.install(c);self.assertFails('count_over_total_source_mismatch')
 def test_pointer_negative_index_and_bad_escape(self):
  for pointer in ['/value/~2','value','/value/-1']:
   with self.subTest(pointer=pointer):c=self.field([1]);c['json_pointer']=pointer;self.install(c);self.assertFails()

class DisplayAndCustody(Fixture):
 def test_fraction_presence_rejects_sign_and_exponent_extensions(self):
  for text in ['-1/3','\u22121/3','1/3e-5','11/3','1/30']:
   with self.subTest(text=text):
    c=self.field(1,'1/3');c['display_format']={'kind':'count_over_total','denominator_pointer':'/denominator'};self.install(c,text);self.assertFails('declared_manuscript_display_absent')
 def test_persisted_display_id_is_checked(self):
  self.install(self.field(1));_,ledger,_=v.verify(self.root,refresh_presence=True);ledger['claims'][0]['id']='other-claim'
  (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_text(json.dumps(ledger));r,_,_=v.verify(self.root);self.assertFalse(r['passed']);self.assertIn('stale_persisted_display_metadata',r['failures'][0]['error'])
 def test_manuscript_sign_flip_is_not_substring_presence(self):
  for value,tex in [(1,'reported=-1'),(-1,'reported=+1')]:
   with self.subTest(value=value):self.install(self.field(value),tex);self.assertFails('declared_manuscript_display_absent')
 def test_manuscript_numeric_suffix_is_not_presence(self):
  self.install(self.field(12),'reported=612');self.assertFails('declared_manuscript_display_absent')
 def test_scientific_notation_and_stacked_notation(self):
  for text in [r'$-5.11591\times10^{-13}$',r'\shortstack[r]{$-5.11591$\\$\times10^{-13}$}']:
   with self.subTest(text=text):self.assertIn(v.numeric_value('-5.11591e-13'),v.manuscript_numbers(text))
 def test_long_scientific_mantissa_is_not_a_hash(self):
  self.assertIn(v.numeric_value('1.1368683772161603e-13'),v.manuscript_numbers(r'$1.1368683772161603\times10^{-13}$'))
 def test_numbers_inside_parameter_bounds(self):
  self.assertIn(v.numeric_value('-12'),v.manuscript_numbers('bounds [-12, 0]'))
 def test_missing_persisted_custody_is_not_release_ready(self):
  self.install(self.field(1));r,_,_=v.verify(self.root);self.assertFalse(r['release_ready']);self.assertIn('missing_persisted_source_binding',r['failures'][0]['error'])
 def test_readonly_rejects_stale_hash_and_explicit_refresh_can_repair(self):
  self.install(self.field(1));r,ledger,_=v.verify(self.root,refresh_presence=True);self.assertTrue(r['passed'])
  p=self.root/'validation/MASTER_CLAIM_LEDGER.json';p.write_text(json.dumps(ledger))
  self.assertTrue(v.verify(self.root)[0]['release_ready'])
  (self.root/'paper/source/chapter.tex').write_text('reported=1\n')
  r,_,_=v.verify(self.root);self.assertFalse(r['release_ready']);self.assertIn('stale_persisted_source_hashes',r['failures'][0]['error'])
  self.assertTrue(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_typed_metadata_cannot_hide_numeric_scalar(self):
  c=self.field(1);path,sha=self.source('x=123\n','meta.txt');m={'id':'meta','bundled_source':path,'source_sha256':sha,'source_locator':'line 1, columns 3-5: x=123','text':'123','metadata_kind':'identifier'}
  self.install(c,metadata=[m]);self.assertFails('invalid_metadata_classification')
 def test_typed_citation_has_no_fake_numeric_value(self):
  c=self.field(1);line=r'\citep{Hawkes1971}';path,sha=self.source(line+'\n','meta.txt');m={'id':'meta','bundled_source':path,'source_sha256':sha,'source_locator':f'line 1, columns 1-{len(line)}: {line}','text':line,'metadata_kind':'citation'}
  self.install(c,metadata=[m]);self.assertTrue(self.result()['passed']);m['value']=971;self.install(c,metadata=[m]);self.assertFails('metadata_must_not_claim_numeric_value')

class CompactCustody(Fixture):
 def write(self,ledger):
  (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_bytes(v.format_ledger(ledger))
 def freeze(self,claim=None,tex=None):
  self.install(claim or self.field(1),tex)
  receipt,ledger,checks=v.verify(self.root,refresh_presence=True)
  self.assertTrue(receipt['release_ready'],receipt['failures']);self.write(ledger)
  return ledger,checks
 def assertReadonlyFails(self,ledger,error):
  self.write(ledger);receipt,_,_=v.verify(self.root)
  self.assertFalse(receipt['release_ready'],receipt)
  self.assertTrue(any(error in row['error'] for row in receipt['failures']),receipt['failures'])
 def legacy(self,ledger,checks):
  legacy=copy.deepcopy(ledger);custody=legacy.pop('display_custody');byid={row['id']:row for row in checks}
  for claim in legacy['claims']:
   check=byid[claim['id']]
   claim['final_display_presence']=dict(check,source_hashes={p:custody['source_hashes'][p] for p in check['source_files']},method=custody['method'])
  return legacy
 def test_shared_custody_and_all_matching_files_reconstruct_legacy_losslessly(self):
  (self.root/'paper/source/second.tex').write_text('x=1',encoding='utf-8')
  claim=self.field(1);claim['final_display_locations']=['chapter.tex','second.tex']
  ledger,checks=self.freeze(claim)
  custody=ledger['display_custody'];presence=ledger['claims'][0]['final_display_presence']
  self.assertEqual(custody['schema'],v.DISPLAY_CUSTODY_SCHEMA)
  self.assertEqual(custody['method'],v.DISPLAY_PRESENCE_METHOD)
  self.assertEqual(set(presence),{'matching_files','binding_sha256'})
  self.assertEqual(presence['matching_files'],['paper/source/chapter.tex','paper/source/second.tex'])
  self.assertEqual(presence['binding_sha256'],v.presence_digest(checks[0]))
  self.assertEqual(set(custody['source_hashes']),set(checks[0]['source_files']))
  self.assertEqual(list(ledger).index('display_custody')+1,list(ledger).index('claims'))
  legacy=self.legacy(ledger,checks);self.write(legacy)
  self.assertTrue(v.verify(self.root)[0]['release_ready'])
  receipt,refreshed,_=v.verify(self.root,refresh_presence=True)
  self.assertTrue(receipt['release_ready']);self.assertEqual(ledger,refreshed)
 def test_shared_source_hash_tampering_fails(self):
  ledger,_=self.freeze();ledger['display_custody']['source_hashes']['paper/source/chapter.tex']='0'*64
  self.assertReadonlyFails(ledger,'stale_persisted_source_hashes')
 def test_missing_or_extra_shared_source_hash_fails(self):
  ledger,_=self.freeze()
  for hashes in [{},{**ledger['display_custody']['source_hashes'],'paper/source/unrelated.tex':'0'*64}]:
   with self.subTest(hashes=hashes):
    changed=copy.deepcopy(ledger);changed['display_custody']['source_hashes']=hashes
    self.assertReadonlyFails(changed,'stale_persisted_source_hashes')
 def test_shared_method_is_verified_not_just_documentary_text(self):
  ledger,_=self.freeze();ledger['display_custody']['method']='numeric substring search'
  self.assertReadonlyFails(ledger,'stale_persisted_display_method')
  self.assertFalse(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_unknown_custody_schema_cannot_downgrade_to_legacy(self):
  ledger,_=self.freeze();ledger['display_custody']['schema']='compact_display_custody_v0'
  self.assertReadonlyFails(ledger,'unsupported_display_custody_schema')
  self.assertFalse(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_matching_files_tampering_fails_even_with_recomputed_binding(self):
  ledger,checks=self.freeze();false=copy.deepcopy(checks[0]);false['matching_files']=[];false['present']=False
  ledger['claims'][0]['final_display_presence']={'matching_files':[],'binding_sha256':v.presence_digest(false)}
  self.assertReadonlyFails(ledger,'stale_persisted_display_metadata')
 def test_derived_display_type_is_bound_without_repeating_display(self):
  ledger,_=self.freeze();ledger['claims'][0]['display']=1
  self.assertReadonlyFails(ledger,'stale_persisted_display_metadata')
 def test_derived_declared_source_order_is_bound_without_repeated_source_files(self):
  (self.root/'paper/source/second.tex').write_text('x=2',encoding='utf-8')
  claim=self.field(1);claim['final_display_locations']=['chapter.tex','second.tex']
  ledger,_=self.freeze(claim);ledger['claims'][0]['final_display_locations'].reverse()
  self.assertReadonlyFails(ledger,'stale_persisted_display_metadata')
 def test_missing_compact_custody_cannot_fall_back_to_legacy(self):
  ledger,_=self.freeze();del ledger['display_custody']
  self.assertReadonlyFails(ledger,'compact_presence_without_custody')
  self.assertFalse(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_missing_compact_per_claim_binding_is_rejected(self):
  ledger,_=self.freeze();del ledger['claims'][0]['final_display_presence']
  self.assertReadonlyFails(ledger,'missing_persisted_source_binding')
 def test_legacy_presence_cannot_be_mixed_into_compact_schema(self):
  ledger,checks=self.freeze();legacy=self.legacy(ledger,checks)
  ledger['claims'][0]['final_display_presence']=legacy['claims'][0]['final_display_presence']
  self.assertReadonlyFails(ledger,'stale_persisted_display_metadata')
  self.assertFalse(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_legacy_method_tampering_is_rejected(self):
  ledger,checks=self.freeze();legacy=self.legacy(ledger,checks)
  legacy['claims'][0]['final_display_presence']['method']='unchecked'
  self.assertReadonlyFails(legacy,'stale_persisted_display_method')
  self.assertFalse(v.verify(self.root,refresh_presence=True)[0]['release_ready'])
 def test_legacy_display_type_tampering_is_rejected(self):
  claim=self.field(1);claim['display']=1
  ledger,checks=self.freeze(claim)
  for altered in [1.0,True]:
   with self.subTest(display=altered):
    legacy=self.legacy(ledger,checks)
    legacy['claims'][0]['final_display_presence']['display']=altered
    self.assertReadonlyFails(legacy,'stale_persisted_display_metadata')
 def test_source_edit_cannot_pass_shared_custody_with_unchanged_numeric_token(self):
  self.freeze();(self.root/'paper/source/chapter.tex').write_text('other words, same value=1',encoding='utf-8')
  receipt,_,_=v.verify(self.root);self.assertFalse(receipt['release_ready'])
  self.assertTrue(any(row['error']=='stale_persisted_source_hashes' for row in receipt['failures']))

if __name__=='__main__':unittest.main(verbosity=2)
