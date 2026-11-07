"""Admission controls using invented identifiers; no scientific execution."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('continuation_controller', ROOT/'scripts/run_continuation.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class AdmissionControls(unittest.TestCase):
    def setUp(self):
        self.registry = {'rows': [{'id': name} for name in ('ordinary', 'large', 'other')]}
        self.proposal = {'row_ids': ['ordinary', 'large']}

    def test_pilot_must_keep_predeclared_order_and_members(self):
        good = {'stage': 'regional-pilot', 'row_ids': ['ordinary', 'large']}
        self.assertEqual(controller.replay_roster(good, self.proposal, self.registry)[0], good['row_ids'])
        for rows in (['large', 'ordinary'], ['ordinary'], ['ordinary', 'large', 'other']):
            with self.assertRaises(ValueError):
                controller.replay_roster(dict(good, row_ids=rows), self.proposal, self.registry)

    def test_completion_requires_accepted_pilot_and_exact_remaining_rows(self):
        good = {'stage': 'cached-completion', 'row_ids': ['other'], 'pilot_output_review_passed': True}
        self.assertEqual(controller.replay_roster(good, self.proposal, self.registry)[0], ['other'])
        for changed in ({'pilot_output_review_passed': False}, {'row_ids': []},
                        {'row_ids': ['ordinary', 'other']}, {'row_ids': ['other', 'other']}):
            with self.assertRaises(ValueError):
                controller.replay_roster(dict(good, **changed), self.proposal, self.registry)

    def test_registry_duplicates_and_unknown_pilot_are_rejected(self):
        good = {'stage': 'regional-pilot', 'row_ids': ['ordinary', 'large']}
        with self.assertRaises(ValueError):
            controller.replay_roster(good, self.proposal, {'rows': self.registry['rows']*2})
        with self.assertRaises(ValueError):
            controller.replay_roster(good, {'row_ids': ['unknown']}, self.registry)

    def test_nested_registry_and_proposal_are_both_mandatory_pins(self):
        review = {'registry': 'reproduction/score_replay/jma/registry.json',
                  'proposal': 'reproduction/score_replay/jma/pilot_proposal.json'}
        pins = controller.mandatory_sources('regional-pilot', review)
        self.assertTrue({review['registry'], review['proposal'],
                         'reproduction/score_replay/jma/input_manifest.json',
                         'reproduction/score_replay/regional_replay.py'}.issubset(pins))
        with self.assertRaises(ValueError):
            controller.replay_paths(dict(review, proposal='reproduction/score_replay/s03/pilot_proposal.json'))
        with self.assertRaises(ValueError):
            controller.replay_paths(dict(review, registry='../outside.json'))

    def test_inhibition_route_requires_its_own_evaluator_and_build_pins(self):
        review = {'registry': 'reproduction/score_replay/s04_original/registry.json',
                  'proposal': 'reproduction/score_replay/s04_original/pilot_proposal.json'}
        pins = controller.mandatory_sources('inhibition-pilot', review)
        self.assertTrue({review['registry'], review['proposal'],
                         'reproduction/score_replay/inhibition_build.py',
                         'reproduction/score_replay/inhibition_replay.py'}.issubset(pins))

    def test_s02_binds_original_oracle_and_new_component_wrapper(self):
        pins = controller.mandatory_sources('s02-pilot')
        self.assertTrue({'reproduction/score_replay/s02_replay.py',
                         'reproduction/score_replay/s02/protocol.json',
                         'reproduction/score_replay/s02/components.cpp',
                         'reproduction/score_replay/s02/original/independent_f_oracle.cpp',
                         'tests/test_s02_score_replay.py'}.issubset(pins))


if __name__ == '__main__':
    unittest.main()
