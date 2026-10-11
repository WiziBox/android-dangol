# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('dangol_vendor', ROOT / 'tools/import_vendor.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
CAL = b'boardtype=0x123\nsromrev=3\nmacaddr=02:00:00:00:00:01\n'


class VendorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'stock'
        (self.root / 'lib').mkdir(parents=True)
        (self.root / 'lib/example.so').write_bytes(b'FIXTURE')
        cal = self.root / tool.CALIBRATION
        cal.parent.mkdir(parents=True)
        cal.write_bytes(CAL)
        self.output = self.root.parent / 'new-vendor'
        self.index = {'schema': 1, 'device': 'dangol', 'redistribution_approved': False,
                      'owner_calibration': tool.CALIBRATION, 'files': [{
                          'source': 'lib/example.so', 'install': 'system/lib/example.so',
                          'bytes': 7, 'sha256': hashlib.sha256(b'FIXTURE').hexdigest()}]}

    def test_dry_run_no_output(self):
        self.assertFalse(tool.stage(self.index, self.root, self.output)['applied'])
        self.assertFalse(self.output.exists())

    def test_apply_calibration_not_in_receipt(self):
        self.assertTrue(tool.stage(self.index, self.root, self.output, True)['applied'])
        receipt = (self.output / 'import-receipt.json').read_text()
        self.assertNotIn('02:00:00', receipt)
        self.assertNotIn(hashlib.sha256(CAL).hexdigest(), receipt)
        self.assertEqual((self.output / 'proprietary/system' / tool.CALIBRATION).read_bytes(), CAL)
        self.assertIn('system/lib/example.so', (self.output / 'dangol-vendor.mk').read_text())

    def test_existing_output_preserved(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            tool.stage(self.index, self.root, self.output, True)

    def test_bad_hash_preflight(self):
        self.index['files'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            tool.stage(self.index, self.root, self.output, True)
        self.assertFalse(self.output.exists())

    def test_credentials_and_key_rejected(self):
        for extra in (b'psk=secret\n', b'network={\n', b'PRIVATE KEY\n', b'\x00', b'macaddr=duplicate\n'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                tool.calibration_valid(CAL + extra)

    def test_unsafe_paths(self):
        for name in ('../escape', '/absolute', '.git/config', 'data/key', 'lib/test.apk', 'lib\\x'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                tool.relative(name)

    def test_public_index_omits_calibration_fingerprint(self):
        index = json.loads((ROOT / 'vendor-inputs/stock.json').read_text())
        self.assertEqual(len(index['files']), 25)
        self.assertNotIn(tool.CALIBRATION, [x['source'] for x in index['files']])
        self.assertFalse(index['redistribution_approved'])
