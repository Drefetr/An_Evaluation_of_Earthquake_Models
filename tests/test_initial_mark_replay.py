"""Constructed initial mark-history CPU replay controls; no historical scoring."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np
from reproduction.score_replay import initial_mark_replay as R


class InitialMarkControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.cpu_build import build_shared
        cls.build = build_shared(R.base.HERE/'components.cpp', Path(tempfile.mkdtemp(prefix='initial-mark-fixture-'))/'native', dependency_root=R.base.HERE)
        if not cls.build['passed']: raise RuntimeError('Constructed native build failed')
        cls.oracle = R.base.load_oracle(); cls.native = cls.oracle.Native(cls.build['library'])
        path = R.HERE/'original/engine/iteration_20/code/restricted_history.py'
        # Original imports use historical top-level module names and prepend a
        # source directory. Keep their isolated module graph alive by object
        # references, without changing later test imports or replacing a public
        # kernel module that was loaded before this fixture.
        names = ('kernels', '_restricted20_cuda_authority', '_iteration17_oracle_cpu_authority',
                 'initial_mark_original_restricted')
        previous = {name: sys.modules[name] for name in names if name in sys.modules}
        old_path = sys.path.copy()
        try:
            for name in names: sys.modules.pop(name, None)
            spec = importlib.util.spec_from_file_location('initial_mark_original_restricted', path)
            cls.original = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.original; spec.loader.exec_module(cls.original)
        finally:
            sys.path[:] = old_path
            for name in names: sys.modules.pop(name, None)
            sys.modules.update(previous)
        cls.kernel = dict(kind='ml', tau=1., alpha=.5, p=1.3, spectral_step=.4, spectral_tail_bound=1e-8)
        cls.law = dict(T=3., coordinate=3., beta=2.849401764894274, gamma=.75*math.log(10),
                       n=.5017751599706763, ratio=.7, stress=cls.kernel, trigger=cls.kernel)
        cls.data = dict(times=np.array([1., 1., 2.]), times_lo=np.array([0., 1e-20, 0.]),
                        event_gaps=np.array([1., 1e-20, 1.]), excess=np.array([.1, .2, .3]))

    def original_history(self):
        o = self.original; kernel = o.KernelSpec(**self.kernel)
        law = o.KnownLaw(-2., .1, self.law['n'], self.law['beta'], .7, 3., kernel, kernel, 3.)
        return o.RestrictedHistory(self.data, law, clock_mode='paired', order=32, backend='cpu')

    def selected_fixture(self):
        original = self.original_history()
        state = self.native.state(self.data, self.law, 'paired', .7, 32, False)
        extra = R.base.Extra(self.native, self.oracle)
        methods = []
        try:
            for name, a, d in [('known_known', -2., .1), ('background_estimated', -1.9, .2)]:
                states = {}
                for phase, eta in [('null', 0.), ('alternative', .2)]:
                    parameters = [a, d, self.law['n'], eta]
                    expected = original.objective(parameters, original.law.trigger, .7, gradient=False)
                    states[phase] = dict(pars=parameters, nll=expected, success=True, ratio=.7, trigger=self.kernel)
                glr = 2*(states['null']['nll']-states['alternative']['nll'])
                methods.append(dict(id=name, complete=True, status='complete', gates=dict(passed=True), **states,
                                    contrast16=dict(statistic=glr), contrast32=dict(statistic=glr),
                                    selected_objectives=[dict(phase=p, cpu32_nll=s['nll'], passed=True) for p, s in states.items()]))
            return methods
        finally:
            state.close(); original.close()

    def test_original_cpu_and_independent_native_selected_score_gradient(self):
        original = self.original_history()
        state = self.native.state(self.data, self.law, 'paired', .7, 32, False)
        try:
            for parameters in ([-2., .1, self.law['n'], 0.], [-1.9, .2, self.law['n'], .2]):
                value, gradient = original.objective(parameters, original.law.trigger, .7)
                actual = state.evaluate(parameters)
                self.assertAlmostEqual(actual[0], value, places=9)
                np.testing.assert_allclose(actual[1:5], gradient, rtol=1e-9, atol=1e-8)
        finally:
            original.close(); state.close()

    def test_full_adapter_on_constructed_history_only(self):
        saved = dict(result=dict(methods=self.selected_fixture()))
        meta = dict(case_id='constructed', skeleton=0, h=0., case='case', history='history', comparison='comparison')
        inputs = SimpleNamespace(law=self.law, case=lambda m: (self.data, saved), members={k: dict(sha256='fixture') for k in ('case', 'history', 'comparison')})
        with tempfile.TemporaryDirectory() as tmp:
            result = R.run_case(meta, inputs, self.oracle, self.native, R.read(R.HERE/'protocol.json'), Path(tmp), math.inf, True)
            self.assertTrue(result['passed'], result.get('error'))
            self.assertEqual(len(result['methods']), 2)
            for method in result['methods']:
                self.assertEqual(method['refinement']['status'], 'executed')
                for row in method['states'].values():
                    self.assertEqual(row['parameters'][2], self.law['n'])
                    self.assertAlmostEqual(row['joint'], row['P']+row['C']+row['M'], places=10)
                    self.assertEqual(row['timing'], -row['nll_ground'])

    def test_original_s02_branching_scalar_cannot_replace_initial_scalar(self):
        method = self.selected_fixture()[0]
        law = dict(a=-2., d=.1, n=self.law['n'], ratio=.7, trigger=self.kernel)
        R.validate_selected(method, law)
        method['null']['pars'][2] = .5
        with self.assertRaisesRegex(ValueError, 'fixed n'): R.validate_selected(method, law)

    def test_known_background_cannot_be_silently_refitted(self):
        method = self.selected_fixture()[0]; method['alternative']['pars'][0] += .01
        with self.assertRaisesRegex(ValueError, 'Known background'):
            R.validate_selected(method, dict(a=-2., d=.1, n=self.law['n'], ratio=.7, trigger=self.kernel))

    def test_failed_saved_scalar_remains_failed_and_retained(self):
        methods = self.selected_fixture(); methods[0]['null']['nll'] += 1.
        inputs = SimpleNamespace(law=self.law, case=lambda m: (self.data, dict(result=dict(methods=methods))), members={k: dict(sha256='fixture') for k in ('case', 'history', 'comparison')})
        with tempfile.TemporaryDirectory() as tmp:
            meta = dict(case_id='constructed', skeleton=0, h=0., case='case', history='history', comparison='comparison')
            result = R.run_case(meta, inputs, self.oracle, self.native, R.read(R.HERE/'protocol.json'), Path(tmp), math.inf, False)
            self.assertFalse(result['passed'])
            self.assertGreater(result['methods'][0]['states']['null']['absolute_nll_delta'], .99)
            self.assertFalse(R.read(Path(tmp)/'constructed.json')['passed'])

    def test_bootstrap_matches_original_analysis_recipe_on_constructed_values(self):
        path = R.HERE/'original/research/magnitude_history/analyse.py'
        spec = importlib.util.spec_from_file_location('initial_mark_original_analysis', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        values = [i/7 for i in range(20)]
        row = R.bootstrap(values, R.read(R.HERE/'protocol.json')['bootstrap']); original = module.bootstrap(values)
        self.assertEqual(row['mean'], original['mean']); self.assertEqual(row['percentile95'], original['percentile95'])
        with self.assertRaises(ValueError): R.bootstrap(values[:-1], R.read(R.HERE/'protocol.json')['bootstrap'])

    def test_source_archive_and_count_based_pilot_are_pinned_without_scoring(self):
        protocol = R.read(R.HERE/'protocol.json'); inputs = R.Inputs(protocol)
        try:
            self.assertEqual(len(inputs.cases), 60)
            maximum = max(inputs.cases, key=lambda r: r['events'])['skeleton']
            self.assertEqual(protocol['pilot'], [r['case_id'] for r in inputs.cases if r['skeleton'] in (0, maximum)])
            self.assertEqual(inputs.law['n'], .5017751599706763)
        finally: inputs.close()

    def test_missing_review_cannot_launch_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'admission.json'; R.write(p, dict(passed=False))
            with self.assertRaisesRegex(ValueError, 'Reviewed admission'):
                R.check_admission(SimpleNamespace(admission=p), R.read(R.HERE/'protocol.json'))

    def test_incomplete_table_roster_fails(self):
        with self.assertRaisesRegex(ValueError, 'table roster'):
            R.table_comparisons([], None, R.read(R.HERE/'protocol.json'))

    def test_sixty_constructed_cases_reconstruct_original_table_analysis(self):
        path = R.HERE/'original/research/magnitude_history/analyse.py'
        spec = importlib.util.spec_from_file_location('initial_mark_constructed_analysis', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        protocol = R.read(R.HERE/'protocol.json'); plan, terminal, records = [], [], []
        for case_id in protocol['roster']:
            skeleton = int(case_id[1:3]); h = float(case_id.rsplit('h', 1)[1].replace('p', '.'))
            meta = dict(case_id=case_id, skeleton=skeleton, h=h, time_seed=skeleton, mark_seed=skeleton+1)
            plan.append(meta); methods, original = [], []
            for method in R.METHODS:
                glr = float(skeleton+h); selected = glr > .001
                methods.append(dict(procedure=method, glr=dict(value=glr), selected=selected, eta=.2))
                original.append(dict(method=method, status='resolved', direct_glr=glr, eta=.2))
            records.append(dict(case_id=case_id, skeleton=skeleton, h=h, passed=True, methods=methods))
            terminal.append(dict(event='case_terminal', **meta, methods=original))
        old_protocol = dict(status='constructed', comparison=dict(operational_selection=dict(direct_glr_above=.001, eta_above=1e-6)),
                            generator=dict(history_strengths=[0., .5, .9]))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); R.write(folder/'plan.json', dict(protocol_sha256='constructed', planned=plan))
            (folder/'registry.jsonl').write_text(''.join(R.json.dumps(row)+'\n' for row in terminal))
            _, summary = module.analyse(folder, old_protocol, 'constructed')
            result = R.table_comparisons(records, SimpleNamespace(json=lambda path: summary), protocol)
            self.assertTrue(result['passed']); self.assertEqual(len(result['cells']), 54)
            records[-1]['methods'][0]['glr']['value'] += 1
            self.assertFalse(R.table_comparisons(records, SimpleNamespace(json=lambda path: summary), protocol)['passed'])


if __name__ == '__main__':
    unittest.main()
