"""Adversarial checks for separated inventories and canonical public authorities."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from test_verify_claims import Fixture, v


class SeparatedInventory(Fixture):
    def install_both(self):
        main = self.field(1)
        source = copy.deepcopy(main)
        source.update(id='inventory', ledger_role='source_inventory_only')
        data = self.install(main)
        data['source_inventory'] = 'validation/SOURCE_INVENTORY.json'
        (self.root/'validation/MASTER_CLAIM_LEDGER.json').write_text(json.dumps(data))
        (self.root/'validation/SOURCE_INVENTORY.json').write_text(json.dumps({'claims': [source]}))
        return source

    def test_default_checks_both_roles(self):
        self.install_both()
        receipt, _, _ = v.verify_ledgers(self.root, refresh_presence=True)
        self.assertTrue(receipt['passed'], receipt['failures'])
        self.assertEqual(receipt['counts']['claims'], 2)
        self.assertEqual(receipt['counts']['literal_manuscript_display_records'], 1)

    def test_missing_declared_inventory_fails(self):
        self.install_both()
        (self.root/'validation/SOURCE_INVENTORY.json').unlink()
        self.assertFalse(v.verify_ledgers(self.root, refresh_presence=True)[0]['passed'])

    def test_removing_inventory_declaration_cannot_hide_secondary_records(self):
        self.install_both()
        path = self.root/'validation/MASTER_CLAIM_LEDGER.json'
        ledger = json.loads(path.read_text())
        del ledger['source_inventory']
        path.write_text(json.dumps(ledger))
        receipt, _, _ = v.verify_ledgers(self.root, refresh_presence=True)
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['failures'][0]['error'], 'source_inventory_declaration_missing')

    def test_inventory_tampering_is_not_hidden_by_passing_manuscript(self):
        source = self.install_both()
        source['value'] = 99
        (self.root/'validation/SOURCE_INVENTORY.json').write_text(json.dumps({'claims': [source]}))
        receipt, _, _ = v.verify_ledgers(self.root, refresh_presence=True)
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['failures'][0]['ledger'], 'validation/SOURCE_INVENTORY.json')

    def test_duplicate_ids_across_ledgers_fail(self):
        source = self.install_both()
        source['id'] = 'sample'
        (self.root/'validation/SOURCE_INVENTORY.json').write_text(json.dumps({'claims': [source]}))
        receipt, _, _ = v.verify_ledgers(self.root, refresh_presence=True)
        self.assertFalse(receipt['passed'])
        self.assertTrue(any(f['error'] == 'duplicate_claim_id_across_ledgers' for f in receipt['failures']))


class PublicPayload(unittest.TestCase):
    def test_resealing_payload_cannot_override_a_changed_authority(self):
        script = Path(__file__).resolve().parents[1]/'scripts/verify_repository.py'
        spec = importlib.util.spec_from_file_location('payload_verifier', script)
        payload = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(payload)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['provenance', 'validation', 'paper/data']:
                (root/directory).mkdir(parents=True)
            (root/'provenance/extraction_manifest.json').write_text('{"files": []}')
            authority = root/'paper/data/catalogue.json'
            authority.write_text('{}')
            (root/'validation/authority_manifest.json').write_text(json.dumps([
                {'bundled_path': 'paper/data/catalogue.json', 'sha256': payload.digest(authority), 'bytes': 2}
            ]))
            self.assertTrue(payload.verify(root, write_manifest=True)['passed'])
            manifest = (root/'MANIFEST.json').read_bytes()
            authority.write_text('{"altered": true}')
            self.assertFalse(payload.verify(root, write_manifest=True)['passed'])
            self.assertEqual(manifest, (root/'MANIFEST.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
