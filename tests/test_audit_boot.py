# SPDX-License-Identifier: Apache-2.0
"""Synthetic parser/security fixtures, not bootability or hardware tests."""
import gzip
import base64
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('audit_boot', Path(__file__).parents[1] / 'tools/audit_boot.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def archive(entries):
    result = bytearray()
    for name, data in entries + [('TRAILER!!!', b'')]:
        encoded = name.encode() + b'\0'
        fields = [1, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0]
        result += b'070701' + b''.join(f'{field:08x}'.encode() for field in fields) + encoded
        result += bytes((-len(result)) % 4)
        result += data
        result += bytes((-len(result)) % 4)
    return bytes(result)


def android(entries):
    ramdisk = gzip.compress(archive(entries), mtime=0)
    header = bytearray(2048)
    header[:8] = b'ANDROID!'
    struct.pack_into('<9I', header, 8, 4, 0, len(ramdisk), 0, 0, 0, 0, 2048, 0)
    return bytes(header) + b'KERN' + bytes(2044) + ramdisk



class AuditTests(unittest.TestCase):
    def test_clean_android(self):
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\nro.secure=1\n')]), 'dangol')
        self.assertTrue(result['boot_key_audit_passed'])
        self.assertFalse(result['publication_approved'])

    def test_adb_keys_rejected_even_empty(self):
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\n'), ('./adb_keys', b'')]), 'dangol')
        self.assertFalse(result['boot_key_audit_passed'])

    def test_private_key_without_key_filename(self):
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\n'), ('notes', b'-----BEGIN PRIVATE KEY-----\nplaceholder')]), 'dangol')
        self.assertFalse(result['boot_key_audit_passed'])
        self.assertNotIn('placeholder', str(result))

    def test_root_default_rejected(self):
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\nro.secure=0\n')]), 'dangol')
        self.assertFalse(result['boot_key_audit_passed'])

    def test_authentication_required(self):
        self.assertFalse(audit.audit_bytes(android([]), 'dangol')['boot_key_audit_passed'])

    def test_path_traversal(self):
        with self.assertRaises(ValueError):
            list(audit.cpio_entries(archive([('../adb_keys', b'x')])))

    def test_duplicate_path(self):
        with self.assertRaises(ValueError):
            list(audit.cpio_entries(archive([('x', b'a'), ('./x', b'b')])))

    def test_truncated_archive(self):
        with self.assertRaises(ValueError):
            list(audit.cpio_entries(archive([('x', b'a')])[:-1]))

    def test_wrong_device(self):
        with self.assertRaises(ValueError):
            audit.audit_bytes(b'unsupported image', 'dangol')

    def test_hidden_adb_public_key(self):
        public_fixture = struct.pack('<I', 64) + bytes(520)
        encoded = base64.b64encode(public_fixture)
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\n'), ('unexpected', encoded)]), 'dangol')
        self.assertFalse(result['boot_key_audit_passed'])

    def test_absolute_archive_path(self):
        with self.assertRaises(ValueError):
            list(audit.cpio_entries(archive([('/adb_keys', b'')])) )

    def test_oversized_expansion(self):
        original_limit = audit.MAX_RAMDISK
        try:
            audit.MAX_RAMDISK = 64
            with self.assertRaises(ValueError):
                audit.audit_bytes(android([('data', bytes(1024))]), 'dangol')
        finally:
            audit.MAX_RAMDISK = original_limit

    def test_no_private_content_in_report(self):
        result = audit.audit_bytes(android([('default.prop', b'ro.adb.secure=1\n'), ('adb_keys', b'PRIVATE_HOST_MARKER')]), 'dangol')
        self.assertNotIn('PRIVATE_HOST_MARKER', str(result))


if __name__ == '__main__':
    unittest.main()
