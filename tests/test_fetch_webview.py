# SPDX-License-Identifier: Apache-2.0
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import hashlib

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
try:
    import fetch_webview as tool
finally:
    sys.path.pop(0)


class Response(io.BytesIO):
    def geturl(self):
        return 'https://official.example.test/object'


class FetchWebViewTests(unittest.TestCase):
    def test_https_only(self):
        self.assertEqual(tool.https_url('https://example.test/object'), 'https://example.test/object')
        for value in ('http://example.test/object', 'file:///private', 'https://user:password@example.test/object'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.https_url(value)

    def test_existing_directory_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            marker = output / 'user-file'
            marker.write_text('KEEP')
            with self.assertRaises(ValueError):
                tool.download('x86', output, mock.Mock())
            self.assertEqual(marker.read_text(), 'KEEP')

    def test_verified_download_and_private_headers_not_recorded(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('lib/x86/libwebviewchromium.so', b'fixture')
        data = data.getvalue()
        oid, size = hashlib.sha256(data).hexdigest(), len(data)
        reply = {'objects': [{'oid': oid, 'size': size, 'actions': {'download': {
            'href': 'https://official.example.test/object',
            'header': {'Authorization': 'temporary-fixture-token'}}}}]}
        opener = mock.Mock()
        opener.open.side_effect = [Response(json.dumps(reply).encode()), Response(data)]
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(tool.INPUTS, {'x86': ('fixture', oid, size)}):
            output = Path(folder) / 'new'
            result = tool.download('x86', output, opener)
            self.assertEqual((output / 'webview.apk').read_bytes(), data)
            self.assertFalse(result['source_modified'])
            self.assertFalse(result['redistribution_approved'])
            self.assertNotIn('temporary-fixture-token', (output / 'download-receipt.json').read_text())

    def test_wrong_lfs_identity_refused_before_output(self):
        opener = mock.Mock()
        opener.open.return_value = Response(json.dumps({'objects': [{'oid': 'wrong', 'size': 1}]}).encode())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'new'
            with self.assertRaises(ValueError):
                tool.download('x86', output, opener)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
