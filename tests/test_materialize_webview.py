# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('materialize_webview', ROOT / 'tools/materialize_webview.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class WebViewTests(unittest.TestCase):
    def fixture(self, folder):
        source = Path(folder) / 'source'
        project = source / 'external/chromium-webview/prebuilt/x86'
        project.mkdir(parents=True)
        asset = Path(folder) / 'asset.apk'
        with zipfile.ZipFile(asset, 'w') as archive:
            archive.writestr('lib/x86/libwebviewchromium.so', b'fixture-not-real-library')
        oid = hashlib.sha256(asset.read_bytes()).hexdigest()
        size = asset.stat().st_size
        target = project / 'webview.apk'
        target.write_bytes(tool.pointer(oid, size))
        return source, asset, target, oid, size

    def test_pinned_metadata(self):
        revision, oid, size = tool.INPUTS['x86']
        self.assertEqual(len(revision), 40)
        self.assertEqual(len(oid), 64)
        self.assertEqual(size, 142423540)
        self.assertEqual(len(tool.pointer(oid, size)), 134)

    def test_dry_run_and_apply_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            source, asset, target, oid, size = self.fixture(folder)
            original = target.read_bytes()
            with mock.patch.dict(tool.INPUTS, {'x86': ('fixture-revision', oid, size)}), mock.patch.object(tool.subprocess, 'check_output', return_value='fixture-revision\n'):
                result = tool.materialize(source, 'x86', asset)
                self.assertTrue(result['dry_run'])
                self.assertEqual(target.read_bytes(), original)
                self.assertTrue(tool.materialize(source, 'x86', asset, True)['changed'])
                self.assertEqual(target.read_bytes(), asset.read_bytes())
                result = tool.materialize(source, 'x86', asset, True)
                self.assertTrue(result['already_materialized'])
                self.assertFalse(result['changed'])
                self.assertFalse(result['redistribution_approved'])

    def test_modified_target_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source, asset, target, oid, size = self.fixture(folder)
            target.write_bytes(b'user-file')
            with mock.patch.dict(tool.INPUTS, {'x86': ('fixture-revision', oid, size)}), mock.patch.object(tool.subprocess, 'check_output', return_value='fixture-revision\n'):
                with self.assertRaises(ValueError):
                    tool.materialize(source, 'x86', asset, True)
            self.assertEqual(target.read_bytes(), b'user-file')

    def test_wrong_asset_preserves_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            source, asset, target, oid, size = self.fixture(folder)
            original = target.read_bytes()
            asset.write_bytes(b'wrong')
            with mock.patch.dict(tool.INPUTS, {'x86': ('fixture-revision', oid, size)}), mock.patch.object(tool.subprocess, 'check_output', return_value='fixture-revision\n'):
                with self.assertRaises(ValueError):
                    tool.materialize(source, 'x86', asset, True)
            self.assertEqual(target.read_bytes(), original)

    def test_wrong_revision_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source, asset, target, oid, size = self.fixture(folder)
            original = target.read_bytes()
            with mock.patch.object(tool.subprocess, 'check_output', return_value='wrong-revision\n'):
                with self.assertRaises(ValueError):
                    tool.materialize(source, 'x86', asset, True)
            self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
