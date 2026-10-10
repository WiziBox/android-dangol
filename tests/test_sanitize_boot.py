# SPDX-License-Identifier: Apache-2.0
"""Synthetic unsigned image fixtures; not hardware/bootability evidence."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from test_audit_boot import android, osip, audit

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
spec = importlib.util.spec_from_file_location('sanitize_boot', Path(__file__).parents[1] / 'tools/sanitize_boot.py')
sanitizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sanitizer)


def unsigned_osip(entries):
    image = bytearray(osip(entries))
    image[8:10] = b'\x01\x01'
    struct.pack_into('<H', image, 10, 56)
    image[52] = 1
    image[7] = 0
    checksum = 0
    for byte in image[:56]:
        checksum ^= byte
    image[7] = checksum
    return bytes(image)


class SanitizeTests(unittest.TestCase):
    entries = [('default.prop', b'ro.adb.secure=0\nro.secure=0\n'), ('adb_keys', b'HOST_APPROVAL_FIXTURE')]

    def test_android_remove_and_secure(self):
        source = android(self.entries)
        result, report = sanitizer.sanitize(source, 'dangol')
        self.assertTrue(report['boot_key_audit_passed'])
        self.assertFalse(report['publication_approved'])
        self.assertFalse(report['bootability_verified'])
        self.assertEqual(result[2048:4096], source[2048:4096])
        self.assertEqual(report['removed_entries'], ['adb_keys'])
        self.assertNotIn('HOST_APPROVAL_FIXTURE', str(report))

    def test_osip_preserves_kernel(self):
        source = unsigned_osip(self.entries)
        result, report = sanitizer.sanitize(source, 'acer-a1-840fhd')
        self.assertTrue(report['boot_key_audit_passed'])
        self.assertEqual(result[0x3200:0x4200], source[0x3200:0x4200])
        checksum = 0
        for byte in result[:56]:
            checksum ^= byte
        self.assertEqual(checksum, 0)
        audit.ramdisk_from_boot(result, 'acer-a1-840fhd')

    def test_repeatable(self):
        source = android(self.entries)
        self.assertEqual(sanitizer.sanitize(source, 'dangol')[0], sanitizer.sanitize(source, 'dangol')[0])

    def test_unknown_private_key_refused(self):
        source = android(self.entries + [('secret', b'-----BEGIN PRIVATE KEY-----')])
        with self.assertRaises(ValueError):
            sanitizer.sanitize(source, 'dangol')

    def test_private_key_file_not_silently_removed(self):
        with self.assertRaises(ValueError):
            sanitizer.sanitize(android(self.entries + [('adbkey', b'')]), 'dangol')

    def test_missing_properties_refused(self):
        with self.assertRaises(ValueError):
            sanitizer.sanitize(android([('adb_keys', b'')]), 'dangol')

    def test_signed_or_unknown_osip_refused(self):
        with self.assertRaises(ValueError):
            sanitizer.sanitize(osip(self.entries), 'acer-a1-840fhd')

    def test_unknown_android_tail_refused(self):
        with self.assertRaises(ValueError):
            sanitizer.sanitize(android(self.entries) + b'SIGNATURE', 'dangol')

    def test_preserve_second_payload(self):
        source = bytearray(android(self.entries))
        source += bytes((-len(source)) % 2048)
        source += b'DTB!'
        struct.pack_into('<I', source, 24, 4)
        result, report = sanitizer.sanitize(bytes(source), 'dangol')
        start = 4096 + audit.align(struct.unpack_from('<I', result, 16)[0], 2048)
        self.assertEqual(result[start:start + 4], b'DTB!')

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.img'
            output = Path(folder) / 'output.img'
            source.write_bytes(android(self.entries))
            output.write_bytes(b'KEEP')
            self.assertEqual(sanitizer.main(['--device', 'dangol', '--input', str(source), '--output', str(output)]), 2)
            self.assertEqual(output.read_bytes(), b'KEEP')
            self.assertEqual(source.read_bytes(), android(self.entries))


if __name__ == '__main__':
    unittest.main()
