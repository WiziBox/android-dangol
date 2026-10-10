# SPDX-License-Identifier: Apache-2.0
"""Temporary Git fixtures only; no real Android source or device mutations."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('apply_patches', Path(__file__).parents[1] / 'tools/apply_patches.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='android-patch-unit-')
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.repository = self.root / 'publication'
        self.source.mkdir()
        self.repository.mkdir()
        self.project = self.source / 'project'
        self.project.mkdir()
        self.run_git('init', '-q')
        self.run_git('config', 'user.name', 'Unit Test')
        self.run_git('config', 'user.email', 'unit@invalid')
        # Force cross-platform fixture diffs to have stable LF bytes.
        self.run_git('config', 'core.autocrlf', 'false')
        (self.project / 'file.txt').write_text('before\n')
        self.run_git('add', 'file.txt')
        self.run_git('commit', '-qm', 'fixture')
        base = self.run_git('rev-parse', 'HEAD').decode().strip()
        (self.project / 'file.txt').write_text('after\n')
        patch_bytes = self.run_git('diff', '--full-index')
        (self.project / 'file.txt').write_text('before\n')
        self.patch = self.repository / 'project.patch'
        self.patch.write_bytes(patch_bytes)
        self.record = {'project': 'project', 'base_commit': base, 'patch': 'project.patch',
                       'sha256': hashlib.sha256(patch_bytes).hexdigest()}
        self.index = self.repository / 'patch-set.json'
        self.write_index([self.record])

    def tearDown(self):
        self.temporary.cleanup()

    def run_git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.project), *arguments], stderr=subprocess.DEVNULL)

    def write_index(self, records):
        self.index.write_text(json.dumps({'schema': 1, 'patches': records}))

    def test_dry_preflight_preserves_source(self):
        plan = tool.preflight(self.source, self.index, self.repository)
        self.assertEqual(len(plan), 1)
        self.assertEqual((self.project / 'file.txt').read_text(), 'before\n')

    def test_apply_checked_patch_to_fixture(self):
        plan = tool.preflight(self.source, self.index, self.repository)
        _, directory, patch = plan[0]
        tool.git(directory, 'apply', str(patch))
        self.assertEqual((self.project / 'file.txt').read_text(), 'after\n')

    def test_wrong_base(self):
        self.record['base_commit'] = '0' * 40
        self.write_index([self.record])
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)

    def test_dirty_project(self):
        (self.project / 'file.txt').write_text('user changes\n')
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)
        self.assertEqual((self.project / 'file.txt').read_text(), 'user changes\n')

    def test_untracked_project_file(self):
        (self.project / 'untracked.txt').write_text('keep me\n')
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)

    def test_wrong_hash(self):
        self.record['sha256'] = '0' * 64
        self.write_index([self.record])
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)

    def test_path_traversal(self):
        self.record['patch'] = '../outside.patch'
        self.write_index([self.record])
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)

    def test_duplicate_project(self):
        self.write_index([self.record, self.record])
        with self.assertRaises(ValueError):
            tool.preflight(self.source, self.index, self.repository)
        self.assertEqual((self.project / 'file.txt').read_text(), 'before\n')


if __name__ == '__main__':
    unittest.main()
