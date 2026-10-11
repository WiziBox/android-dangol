# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path
import unittest
import tempfile
import subprocess
sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from check_publication_inputs import inspect_file, staged_inputs


class PublicationTests(unittest.TestCase):
    def test_private_paths(self):
        for name in ('adbkey', 'root/adb_keys', 'backup/receipt.json', 'system.img',
                     'vendor/module.ko', 'owner.p12', 'id_ed25519'):
            self.assertIsNotNone(inspect_file(name, b''))
    def test_key_headers(self):
        for kind in ('RSA ', 'EC ', 'OPENSSH ', 'ENCRYPTED ', ''):
            data = ('-----BEGIN ' + kind + 'PRIVATE KEY-----\nopaque\n').encode()
            self.assertEqual(inspect_file('notes.txt', data), 'private-key-header')
    def test_code_mentions_not_secret(self):
        self.assertIsNone(inspect_file('tools/check.py', b"pattern = b'-----BEGIN RSA PRIVATE KEY-----'\n"))
    def test_backup_receipt(self):
        self.assertEqual(inspect_file('receipt.json', b'{"schema":1,"device":"dangol","files":{"dangol-system.img":{}}}'),
                         'private-owner-backup-receipt')
    def test_public_text(self):
        self.assertIsNone(inspect_file('README.md', b'Public instructions'))

    def test_staged_secret_survives_clean_working_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp)
            subprocess.run(['git', '-C', temp, 'init', '-q'], check=True)
            path = repository / 'notes.txt'
            secret = ('-----BEGIN ' + 'RSA PRIVATE KEY-----\nfixture\n').encode()
            path.write_bytes(secret)
            subprocess.run(['git', '-C', temp, 'add', 'notes.txt'], check=True)
            path.write_bytes(b'clean working copy')
            rows = list(staged_inputs(repository))
            self.assertEqual(rows, [('notes.txt', secret)])
            self.assertEqual(inspect_file(*rows[0]), 'private-key-header')
