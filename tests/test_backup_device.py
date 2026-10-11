# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_device_preflight import fixture
import backup_device as tool


class BackupTests(unittest.TestCase):
    def values(self):
        values = fixture()
        values['cat /proc/self/mountinfo'] = '1 0 179:3 / /system ro - ext4 /dev/block/mmcblk0p3 ro'
        values[tool.PREBOOT_READ + ' 2>/dev/null | sha256sum'] = hashlib.sha256(b'test').hexdigest() + '  -'
        for number, dev in {1:'179:1',2:'179:2',3:'179:3',5:'179:5',7:'179:7',8:'259:0'}.items():
            values['cat /sys/class/block/mmcblk0p%d/dev' % number] = dev
            block = '/dev/block/mmcblk0p%d' % number
            values['sha256sum ' + block] = hashlib.sha256(b'test').hexdigest() + '  ' + block
        return values
    def test_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'new'
            report = tool.backup(self.values().__getitem__, None, output, 'PRIVATE')
            self.assertFalse(output.exists())
            self.assertTrue(report['dry_run'])
    def test_writable_mount_refused(self):
        with self.assertRaises(ValueError):
            tool.require_read_only_mounts('1 0 179:3 / /system rw - ext4 /dev/block/mmcblk0p3 rw')
    def test_short_preboot_and_bad_hash_refused(self):
        for payload in (b'x', b'fail'):
            with tempfile.TemporaryDirectory() as temp, patch.object(tool, 'PREBOOT_BYTES', 4):
                with self.assertRaises(ValueError):
                    tool.capture_preboot(self.values().__getitem__, lambda cmd, stream: stream.write(payload), Path(temp))
    def test_host_capture_checks_and_private_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'new'
            sizes = {name:4 for name in tool.PARTITIONS}
            with patch.dict(tool.PARTITIONS, sizes, clear=True), patch.object(tool, 'PREBOOT_BYTES', 4):
                report = tool.backup(self.values().__getitem__, lambda cmd, stream: stream.write(b'test'), output, 'PRIVATE', True)
            self.assertTrue(report['backup_created'])
            self.assertNotIn('PRIVATE', str(report))
            self.assertTrue((output / 'backup-receipt.json').is_file())
            self.assertEqual((output / 'dangol-preboot.bin').read_bytes(), b'test')
    def test_corrupt_capture_preserved_and_no_success_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'new'
            sizes = {name:4 for name in tool.PARTITIONS}
            with patch.dict(tool.PARTITIONS, sizes, clear=True), patch.object(tool, 'PREBOOT_BYTES', 4), self.assertRaises(ValueError):
                tool.backup(self.values().__getitem__, lambda cmd, stream: stream.write(b'fail'), output, 'PRIVATE', True)
            self.assertTrue((output / 'dangol-preboot.bin').is_file())
            self.assertFalse((output / 'backup-receipt.json').exists())
