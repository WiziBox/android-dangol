# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).parents[1]


class SourceMetadataTests(unittest.TestCase):
    def test_patch_index_matches_files(self):
        index = json.loads((ROOT / 'patch-set.json').read_text())
        self.assertEqual(index['schema'], 1)
        self.assertEqual(len(index['patches']), 11)
        self.assertEqual(len({entry['project'] for entry in index['patches']}), 11)
        for entry in index['patches']:
            payload = (ROOT / entry['patch']).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), entry['sha256'])
            self.assertRegex(entry['base_commit'], r'^[0-9a-f]{40}$')
            paths = [path.decode().strip() for path in re.findall(rb'^\+\+\+ b/(.+)$', payload, re.M)]
            self.assertEqual(paths, entry['modified_files'])

    def test_manifest_is_pinned_and_public(self):
        manifest = ET.parse(ROOT / 'manifests/upstream.xml').getroot()
        projects = manifest.findall('project')
        self.assertEqual(len(projects), 709)
        remotes = {remote.get('name'): remote.get('fetch') for remote in manifest.findall('remote')}
        self.assertEqual(remotes, {'aosp': 'https://android.googlesource.com/', 'github': 'https://github.com/'})
        self.assertFalse(manifest.findall('repo-hooks'))
        for project in projects:
            self.assertRegex(project.get('revision', ''), r'^[0-9a-f]{40}$')
            self.assertNotEqual(project.get('remote'), 'private')


if __name__ == '__main__':
    unittest.main()
