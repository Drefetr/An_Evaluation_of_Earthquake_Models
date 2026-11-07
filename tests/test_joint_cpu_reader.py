"""Public-reader controls on invented records and the existing tiny full-case fixture."""
import argparse
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from scripts import fit_joint_cpu as reader
import test_joint_execution_driver as existing
import test_joint_budgeted_driver as records


class ScientificDelegateControls(existing.FullCaseEquivalence):
    def test_delegated_full_case_matches_serial_science_exactly(self):
        original = existing.driver.runner_with_scheduler
        # The existing fixture makes four complete eight-start fit records using
        # an invented fixed-return solver, then all five outcomes. Route it via
        # the new public adapter; no archived history or real optimizer is used.
        with patch.object(reader, 'context', return_value=SimpleNamespace(runner_with_scheduler=original)), \
                patch.object(existing.driver, 'runner_with_scheduler', side_effect=reader.make_delegate) as delegate:
            super().test_delegated_full_case_matches_serial_science_exactly()
            self.assertEqual(delegate.call_count, 2)


class PlanningControls(unittest.TestCase):
    def args(self, output):
        return argparse.Namespace(output=output, phase='all', resume=None, continue_published=None,
                                  wall_seconds=100., rss_mib=6144., headroom_mib=2048., max_cases=None,
                                  compiler=None, execution_record=None)

    def test_fresh_caps_and_no_historical_expiry_or_review_claim(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(reader, 'scientific_identity',
                return_value=({'sequence': list('abc')}, {'pilot': ['a']}, {'x': 'hash'})):
            request = reader.plan(self.args(Path(temp)/'out'))
            self.assertEqual(request['sequence'], list('abc'))
            self.assertEqual(request['verification_kind'], 'automated_local_integrity')
            self.assertIsNone(request['published'])
            self.assertNotIn('independent_review_passed', request)
            self.assertNotIn('historical_expires_utc', request)
            for value in (None, 0, -1, float('inf'), float('nan'), True):
                args = self.args(Path(temp)/'out'); args.wall_seconds = value
                with self.assertRaises(ValueError): reader.plan(args)

    def test_published_fixed_slot_and_fresh_mode_are_distinct(self):
        selected = dict(slot={'wall_seconds': 420}, historical_expires_utc='2099-01-01T00:00:00+00:00')
        with tempfile.TemporaryDirectory() as temp, patch.object(reader, 'scientific_identity',
                return_value=({'sequence': list('abc')}, {'pilot': ['a']}, {})), \
                patch.object(reader, 'published_selection', return_value=selected):
            args = self.args(Path(temp)/'out'); args.continue_published = 'budgeted06'; args.wall_seconds = None
            self.assertEqual(reader.plan(args)['wall_seconds'], 420)
            for key, value in [('wall_seconds', 421), ('rss_mib', 4096), ('phase', 'pilot'),
                               ('max_cases', 2), ('resume', Path(temp)), ('compiler', 'g++')]:
                changed = copy.copy(args); setattr(changed, key, value)
                with self.assertRaises(ValueError): reader.plan(changed)
            selected['historical_expires_utc'] = '2000-01-01T00:00:00+00:00'
            with self.assertRaisesRegex(ValueError, 'expired'): reader.plan(args)

    def test_zip_restoration_checks_paths_and_preserves_original_bytes(self):
        for malicious in (None, '../escaped', 'science/../../escape', 'C:/escape'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); archive = root/'input.zip'; out = root/'out'; out.mkdir()
                raw = b'{"cases": []}\n'
                original_failure = b'invented original failed-pilot ZIP bytes'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('science/index.json', raw); z.writestr('build/attenuation.so', b'invented library')
                    z.writestr('build/build_receipt.json', b'{}')
                    z.writestr('original_failure.zip', original_failure)
                    z.writestr('prior/unneeded', b'not copied')
                    if malicious:
                        info=zipfile.ZipInfo('placeholder'); info.filename=malicious
                        z.writestr(info, b'bad')
                selection = dict(archive='input.zip', archive_sha256=reader.sha(archive),
                                 index_sha256=hashlib.sha256(raw).hexdigest(),
                                 original_failure_sha256=hashlib.sha256(original_failure).hexdigest())
                with patch.object(reader, 'ROOT', root):
                    if malicious:
                        with self.assertRaises(ValueError): reader.restore_published(selection, out)
                    else:
                        restored = reader.restore_published(selection, out)
                        self.assertEqual((restored/'science/index.json').read_bytes(), raw)
                        self.assertEqual((out/'build/attenuation.so').read_bytes(), b'invented library')
                        self.assertFalse((restored/'prior').exists())
                        self.assertEqual((out/'original_failure.zip').read_bytes(), original_failure)
                        self.assertEqual((out/'published_previous.zip').read_bytes(), archive.read_bytes())
                        self.assertNotEqual(reader.sha(out/'original_failure.zip'), reader.sha(archive))
        with self.assertRaises(ValueError): reader.safe(Path('.'), 'science\\escape')

    def test_actual_published_roster_metadata_without_scientific_calls(self):
        value=reader.published_selection('budgeted06')
        self.assertEqual(value['case_id'], 'S4_narrow_short_imm_seed410403')
        self.assertEqual(value['slot']['wall_seconds'], 2520)
        self.assertEqual(len(value['source_reviews']), 2)

    def test_optional_genuine_record_binds_sources_predecessor_and_caps(self):
        from experiments.s04b_joint_budgeted import driver as budgeted
        with tempfile.TemporaryDirectory() as temp, patch.object(budgeted,'source_identity',return_value={}):
            root=Path(temp); (root/'source.py').write_bytes(b'invented source')
            request=dict(mode='published_continuation',published=dict(case_id='a',archive_sha256='archive',
                         index_sha256='index',historical_expires_utc='2099-01-01T00:00:00+00:00'),wall_seconds=420,
                         rss_cap_bytes=6,headroom_bytes=2,source_sha256={'source.py':reader.sha(root/'source.py')})
            record=dict(case_ids=['a'],wall_cap_seconds=420,rss_cap_bytes=6,host_headroom_bytes=2,
                        prior_archive_sha256='archive',prior_index_sha256='index',operational_run_config_sha256='a'*64,
                        reviewed_files_sha256=request['source_sha256'],expires_utc='2098-01-01T00:00:00+00:00',
                        numerical_attempt_id='genuine-attempt')
            path=root/'record.json';reader.write(path,record)
            with patch.object(reader,'ROOT',root):
                self.assertEqual(reader.execution_record(path,request),record)
                record['wall_cap_seconds']=421;reader.write(path,record)
                with self.assertRaisesRegex(ValueError,'resource'):reader.execution_record(path,request)
                record['wall_cap_seconds']=420;record['reviewed_files_sha256']={};reader.write(path,record)
                with self.assertRaisesRegex(ValueError,'source/input'):reader.execution_record(path,request)

    def test_worker_source_pin_failure_precedes_science(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); request = root/'request.json'
            reader.write(request, {'source_sha256': {'missing.py': 'changed'}})
            with patch.dict(reader.os.environ, JOINT_READER_REQUEST_SHA256=reader.sha(request)), \
                    patch.object(reader, 'execute_fresh') as call:
                with self.assertRaises((ValueError, FileNotFoundError)): reader.worker(request)
                call.assert_not_called()


class FreshExecutionControls(unittest.TestCase):
    def exercise(self, root, count=3, fail=None, max_cases=None, resume=None):
        output = root/'out'; output.mkdir()
        sequence = ['case'+str(i) for i in range(count)]
        cases = [dict(case_id=n, n_train=3, n_test=3) for n in sequence]
        runtime = {'essential': {'fixture': True}}
        op = {'sequence': sequence}; science = {'pilot': sequence[:1]}
        legacy = SimpleNamespace(SCIENCE=root, verify_protocol=lambda:(op, science),
            frozen=SimpleNamespace(verify_inputs=lambda p:cases, runtime_identity=lambda:runtime),
            model=SimpleNamespace(archived=lambda:{}, Native=lambda p:None),
            OrderedChunkScheduler=contextlib.nullcontext, verify_case=existing.driver.verify_case,
            final_summary=lambda index,p,out,deadline:'invented-summary')
        calls = []
        def case_run(case, modules, native, protocol, out, deadline, prior):
            self.assertIsNone(prior)
            calls.append(case['case_id'])
            # Reuse only the invented record constructor, not any real inputs.
            entry, value = records.report(out.parent, case['case_id'], case['case_id'] != fail)
            return value
        def build(source, destination, dependencies, compiler):
            destination.mkdir(); (destination/'attenuation.so').write_bytes(b'invented')
            receipt={'passed': True, 'library': str(destination/'attenuation.so')}
            reader.write(destination/'build_receipt.json', receipt); return receipt
        request = dict(source_sha256={'x':'pin'}, resume=resume, compiler=None, phase='all',
                       max_cases=max_cases, attempt_id='fixture', sequence=sequence)
        with patch.object(reader, 'context', return_value=legacy), \
                patch.object(reader, 'make_delegate', return_value=SimpleNamespace(case_run=case_run)), \
                patch.object(reader, 'run_controls', return_value=[{'passed':True}]), \
                patch('engine.cpu_build.build_shared', side_effect=build):
            code = reader.execute_fresh(request, output, time.monotonic(), time.monotonic()+30)
        return code, reader.read(output/'science/result.json'), reader.read(output/'science/index.json'), calls

    def test_constructed_full80_has_exact320_arms_and400_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            code, result, index, calls = self.exercise(Path(temp), count=80)
            self.assertEqual(code, 0); self.assertTrue(result['scientific_completion'])
            self.assertEqual(len(calls), 80); self.assertEqual(len(set(calls)), 80)
            self.assertEqual(sum(e['new_fit_arms'] for e in index['cases']), 320)
            self.assertEqual(sum(len(reader.read(Path(temp)/'out/science'/e['file'])['outcomes'])
                                 for e in index['cases']), 400)
            self.assertEqual(result['summary_sha256'], 'invented-summary')

    def test_bounded_prefix_does_not_claim_all80(self):
        with tempfile.TemporaryDirectory() as temp:
            code, result, index, calls = self.exercise(Path(temp), count=80, max_cases=2)
            self.assertEqual(code, 0); self.assertEqual(calls, ['case0','case1'])
            self.assertFalse(result['scientific_completion']); self.assertFalse(result['phase_complete'])
            self.assertIsNone(index['partial_case'])

    def test_failure_retains_partial_and_does_not_replace_or_continue(self):
        with tempfile.TemporaryDirectory() as temp:
            code, result, index, calls = self.exercise(Path(temp), fail='case1')
            self.assertEqual(code, 1); self.assertEqual(calls, ['case0','case1'])
            self.assertFalse(result['scientific_completion'])
            self.assertEqual(index['partial_case']['case_id'], 'case1')
            self.assertEqual(len(index['cases']), 1)
            self.assertFalse(reader.read(Path(temp)/'out/science'/index['attempts'][0]['file'])['passed'])


class ResumeAndTerminalControls(unittest.TestCase):
    def prior(self, root):
        parent=root/'parent'; parent.mkdir(); science=parent/'science'; science.mkdir()
        entry,_=records.report(science,'a')
        (parent/'build').mkdir(); (parent/'build/attenuation.so').write_bytes(b'invented')
        reader.write(parent/'build/build_receipt.json', {'passed':True})
        receipt=dict(attempt_id='old',wall_seconds=3.)
        reader.write(science/'attempts/old.json',receipt)
        index=dict(schema=reader.SCHEMA,partial_case=None,source_sha256={'x':'pin'},sequence=['a','b'],
                   runtime={'essential':{'fixture':True}},cases=[entry],library_sha256=reader.sha(parent/'build/attenuation.so'),
                   build_receipt_sha256=reader.sha(parent/'build/build_receipt.json'),charged_scientific_seconds=3.,
                   attempts=[dict(attempt_id='old',seconds=3.,file='attempts/old.json',sha256=reader.sha(science/'attempts/old.json'))])
        reader.write(science/'index.json',index)
        reader.write(parent/'supervision/result.json',{'status':'passed','survivors_after_cleanup':[]})
        reader.write(parent/'reader_result.json',dict(resume_eligible=True,index_sha256=reader.sha(science/'index.json'),
                    supervision_sha256=reader.sha(parent/'supervision/result.json')))
        request=dict(resume=str(parent),resume_reader_sha256=reader.sha(parent/'reader_result.json'),
                     resume_index_sha256=reader.sha(science/'index.json'),source_sha256={'x':'pin'},sequence=['a','b'])
        return parent,index,request

    def test_own_complete_prefix_copy_is_exact_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); parent,index,request=self.prior(root); output=root/'out'; output.mkdir()
            got,lib=reader.copy_fresh_prefix(request,output,[dict(case_id='a',n_train=3,n_test=3)],index['runtime'])
            self.assertEqual(got,index); self.assertEqual(lib.read_bytes(),b'invented')
            self.assertEqual((output/'science/cases/a.json').read_bytes(),(parent/'science/cases/a.json').read_bytes())
            (parent/'science/cases/a.json').write_text('{}')
            other=root/'other'; other.mkdir()
            with self.assertRaises((ValueError,KeyError)): reader.copy_fresh_prefix(request,other,[],index['runtime'])

    def test_partial_or_changed_runtime_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); parent,index,request=self.prior(root); output=root/'out'; output.mkdir()
            with self.assertRaisesRegex(ValueError,'runtime'): reader.copy_fresh_prefix(request,output,[],{'essential':{}})
            index['partial_case']={'case_id':'b'}; reader.write(parent/'science/index.json',index)
            request['resume_index_sha256']=reader.sha(parent/'science/index.json')
            terminal=reader.read(parent/'reader_result.json');terminal['index_sha256']=request['resume_index_sha256']
            reader.write(parent/'reader_result.json',terminal);request['resume_reader_sha256']=reader.sha(parent/'reader_result.json')
            with self.assertRaisesRegex(ValueError,'Partial'): reader.copy_fresh_prefix(request,output,[],index['runtime'])

    def test_terminal_requires_successful_supervision_and_index_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); reader.write(root/'request.json',{})
            reader.write(root/'science/index.json',{'cases':[{}],'partial_case':None})
            reader.write(root/'science/result.json',dict(passed=True,index_sha256=reader.sha(root/'science/index.json'),scientific_completion=False))
            reader.write(root/'supervision/result.json',dict(status='passed',survivors_after_cleanup=[]))
            result=reader.terminal({'mode':'fresh'},root,0)
            self.assertTrue(result['passed']);self.assertTrue(result['resume_eligible'])
            reader.write(root/'supervision/result.json',dict(status='failed',survivors_after_cleanup=[]))
            self.assertFalse(reader.terminal({'mode':'fresh'},root,0)['passed'])


if __name__ == '__main__':
    unittest.main()
