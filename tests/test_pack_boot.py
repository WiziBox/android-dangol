# SPDX-License-Identifier: Apache-2.0
import gzip
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from test_audit_boot import archive

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
spec = importlib.util.spec_from_file_location('dangol_pack', Path(__file__).resolve().parents[1] / 'tools/pack_boot.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    kernel = bytearray(2048)
    kernel[56:60] = b'ARM\x64'
    dtb = bytearray(64)
    struct.pack_into('>10I', dtb, 0, 0xd00dfeed, 64, 40, 56, 40, 17, 16, 0, 8, 16)
    header = bytearray(2048)
    header[:8] = b'ANDROID!'
    struct.pack_into('<10I', header, 8, len(kernel), module.GEOMETRY[0], 10, module.GEOMETRY[1], len(dtb), module.GEOMETRY[2], module.GEOMETRY[3], 2048, 0, 0x0e04111a)
    header[48:64] = b'PRIVATE-ID-TEST!'
    return bytes(header + kernel + b'oldramdisk' + bytes(2038) + dtb + bytes(1984))


class PackTests(unittest.TestCase):
    def ramdisk(self, entries=None):
        return gzip.compress(archive(entries or [('default.prop', b'ro.secure=1\nro.adb.secure=1\n')]), mtime=0)

    def test_pack_clean(self):
        result, report = module.pack(fixture(), self.ramdisk())
        self.assertNotIn(b'PRIVATE-ID-TEST!', result)
        self.assertNotIn(b'oldramdisk', result)
        self.assertEqual(struct.unpack_from('<I', result, 44)[0], 0)
        self.assertTrue(report['boot_key_audit_passed'])
        self.assertFalse(report['publication_approved'])
        self.assertEqual(report['uboot_read_sectors'], len(result) // 512)

    def test_wrong_geometry(self):
        image = bytearray(fixture())
        struct.pack_into('<I', image, 12, 0)
        with self.assertRaises(ValueError):
            module.pack(bytes(image), self.ramdisk())

    def test_nonzero_trailer(self):
        with self.assertRaises(ValueError):
            module.pack(fixture() + b'signature', self.ramdisk())

    def test_credentials(self):
        with self.assertRaises(ValueError):
            module.pack(fixture(), self.ramdisk([('default.prop', b'ro.adb.secure=1\n'), ('adb_keys', b'')]))

    def test_wrong_dtb(self):
        image = bytearray(fixture())
        image[6144] = 0
        with self.assertRaises(ValueError):
            module.pack(bytes(image), self.ramdisk())

    def test_dry_run_and_existing_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'stock.img').write_bytes(fixture())
            (base / 'ramdisk.img').write_bytes(self.ramdisk())
            args = ['--template', str(base / 'stock.img'), '--ramdisk', str(base / 'ramdisk.img'), '--output', str(base / 'new.img')]
            self.assertEqual(module.main(args), 0)
            self.assertFalse((base / 'new.img').exists())
            self.assertEqual(module.main(args + ['--apply']), 0)
            original = (base / 'new.img').read_bytes()
            self.assertEqual(module.main(args + ['--apply']), 2)
            self.assertEqual((base / 'new.img').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
