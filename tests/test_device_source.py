# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]


class DeviceSourceTests(unittest.TestCase):
    def test_hwc_source_provenance(self):
        index = json.loads((ROOT / 'source/dangol-hwc-provenance.json').read_text())
        self.assertEqual(index['schema'], 1)
        self.assertEqual(len(index['files']), 32)
        self.assertEqual(sum(item['modified'] for item in index['files']), 6)
        for item in index['files']:
            path = ROOT / item['path']
            self.assertTrue(path.resolve().is_relative_to((ROOT / 'source').resolve()))
            payload = path.read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item['published_sha256'])
            self.assertEqual(item['license'], 'Apache-2.0')
            self.assertIn(b'Licensed under the Apache License, Version 2.0', payload)
            self.assertRegex(item['base_commit'], r'^[0-9a-f]{40}$')
            self.assertTrue(item['upstream'].startswith('https://github.com/NexellCorp/'))
            if item['modified']:
                self.assertIn(b'Modified during the WiziBox Dangol Android 9 port', payload)


if __name__ == '__main__':
    unittest.main()
