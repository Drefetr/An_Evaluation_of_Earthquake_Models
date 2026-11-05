"""Withdrawal keeps the old evidence verifiable without claiming current display."""
import copy
import json
import zipfile

from test_verify_claims import Fixture, v


class ExplicitWithdrawal(Fixture):
    def install_withdrawal(self):
        claim = self.field(7)
        self.install(claim)
        receipt, baseline, _ = v.verify(self.root, refresh_presence=True)
        self.assertTrue(receipt['passed'])
        raw = v.format_ledger(baseline)
        members = {'validation/MASTER_CLAIM_LEDGER.json': raw,
                   'paper/source/chapter.tex': b'7'}
        archive = self.root/'validation/baseline.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, payload in members.items():
                z.writestr(name, payload)
        self.record = {
            'schema': 'claim_withdrawals_v1',
            'archive': {'path': 'validation/baseline.zip',
                        'sha256': v.digest(archive.read_bytes()),
                        'members': {name: v.digest(payload) for name, payload in members.items()}},
            'withdrawals': [{'id': 'sample', 'reason': 'Required fitted state is unavailable.'}],
        }
        self.ledger = copy.deepcopy(baseline)
        self.ledger['withdrawal_records'] = ['validation/withdrawal.json']
        self.ledger['claims'][0].update(ledger_role='withdrawn_historical_result',
                                        withdrawal_record='validation/withdrawal.json')
        (self.root/'paper/source/chapter.tex').write_text('Current results only.')
        self.save()

    def save(self):
        (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_bytes(v.format_ledger(self.ledger))
        (self.root/'validation/withdrawal.json').write_text(json.dumps(self.record))

    def test_withdrawn_result_is_verified_but_not_a_current_display(self):
        self.install_withdrawal()
        receipt, refreshed, _ = v.verify(self.root, refresh_presence=True)
        self.assertTrue(receipt['passed'], receipt['failures'])
        self.assertEqual(receipt['counts']['withdrawn_historical_records'], 1)
        self.assertEqual(receipt['counts']['literal_manuscript_display_records'], 0)
        self.assertEqual(receipt['counts']['json_pointer_verified'], 1)
        (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_bytes(v.format_ledger(refreshed))
        self.assertTrue(v.verify(self.root)[0]['passed'])

    def test_archive_mutation_fails(self):
        self.install_withdrawal()
        with (self.root/'validation/baseline.zip').open('ab') as f:
            f.write(b'changed')
        self.assertFails('withdrawal_archive_hash_mismatch')

    def test_withdrawal_cannot_rewrite_old_claim(self):
        self.install_withdrawal()
        self.ledger['claims'][0]['final_display_locations'] = ['elsewhere.tex']
        self.save()
        self.assertFails('withdrawn_claim_changed_from_baseline')

    def test_authority_still_checked(self):
        self.install_withdrawal()
        (self.root/'validation/authorities/source.json').write_text('{"value":8}')
        self.assertFails('source_hash_mismatch')

    def test_silent_demotion_rejected(self):
        self.install_withdrawal()
        self.ledger['claims'][0]['ledger_role'] = 'source_inventory_only'
        self.save()
        self.assertFails('withdrawal_requires_historical_role')

    def test_unlisted_withdrawal_rejected(self):
        self.install_withdrawal()
        self.record['withdrawals'] = []
        self.save()
        self.assertFails('withdrawal_not_explicitly_listed')

    def test_missing_withdrawn_row_rejected(self):
        self.install_withdrawal()
        self.ledger['claims'] = [self.field(1)]
        self.ledger['claims'][0]['id'] = 'replacement'
        self.ledger['claims'][0]['ledger_role'] = 'source_inventory_only'
        self.save()
        self.assertFails('withdrawal_roster_incomplete')

    def test_registry_must_be_declared(self):
        self.install_withdrawal()
        self.ledger.pop('withdrawal_records')
        self.save()
        self.assertFails('undeclared_withdrawal_record')

    def test_uncompiled_source_cannot_be_counted_as_current_manuscript(self):
        self.install(self.field(7))
        (self.root/'paper/source/main.tex').write_text('Current manuscript without input.')
        self.assertFails('declared_manuscript_source_not_compiled')

    def test_literal_input_tree_is_current(self):
        self.install(self.field(7))
        (self.root/'paper/source/main.tex').write_text(r'\input{chapter}')
        self.assertTrue(self.result()['passed'])

    def test_commented_input_does_not_restore_current_status(self):
        self.install(self.field(7))
        (self.root/'paper/source/main.tex').write_text('% '+r'\input{chapter}')
        self.assertFails('declared_manuscript_source_not_compiled')
