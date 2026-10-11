# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_device_preflight import fixture
from test_inspect_system import filesystem
import flash_system as tool


class FlashTests(unittest.TestCase):
    def values(self, sha):
        values = fixture()
        values.update({'getprop ro.bootmode':'recovery',
                       'test -f /tmp/recovery.log && echo RECOVERY':'RECOVERY',
                       'cat /sys/class/block/mmcblk0p3/dev':'179:3',
                       'readlink -f /dev/block/mmcblk0p3':'/dev/block/mmcblk0p3',
                       'cat /proc/self/mountinfo':'1 0 179:6 / /cache rw - ext4 /dev/block/mmcblk0p6 rw',
                       'sync':'', 'sha256sum /dev/block/mmcblk0p3':sha + '  /dev/block/mmcblk0p3'})
        return values
    def invoke(self, apply=False, corrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            data = filesystem()
            source = Path(temp) / 'source.img'
            source.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            values = self.values('0' * 64 if corrupt else sha)
            writes = []
            def write(command, stream):
                writes.append((command, stream.read()))
            with patch.object(tool, 'SIZE', len(data)), patch.object(tool, 'owner_backup'):
                result = tool.install(values.__getitem__, write, source, sha, Path(temp), 'PRIVATE', apply)
            return result, writes, data
    def test_dry_run_no_write(self):
        report, writes, _ = self.invoke()
        self.assertFalse(report['device_written'])
        self.assertEqual(writes, [])
    def test_exact_system_only_stream_and_readback(self):
        report, writes, data = self.invoke(True)
        self.assertEqual(writes, [('dd of=/dev/block/mmcblk0p3 bs=1048576', data)])
        self.assertTrue(report['system_readback_verified'])
        self.assertFalse(report['rebooted'])
    def test_readback_mismatch_not_success(self):
        with self.assertRaises(ValueError):
            self.invoke(True, True)
    def test_recovery_and_unmounted_required(self):
        for key, value in [('getprop ro.bootmode', 'normal'),
                           ('test -f /tmp/recovery.log && echo RECOVERY', ''),
                           ('cat /proc/self/mountinfo', '1 0 179:3 / /alias ro - ext4 /dev/block/mmcblk0p3 ro')]:
            values = self.values('0' * 64)
            values[key] = value
            with self.assertRaises(ValueError):
                tool.recovery_guard(values.__getitem__)
    def test_backup_serial_and_malformed_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'backup-receipt.json').write_text(json.dumps({'files':{}}))
            (root / 'owner-device-record.json').write_text(json.dumps({'schema':1,'device':'dangol','serial':'OTHER','files':{}}))
            with self.assertRaises(ValueError):
                tool.owner_backup(root, 'PRIVATE')
            (root / 'backup-receipt.json').write_text('[]')
            with self.assertRaises(ValueError):
                tool.owner_backup(root, 'PRIVATE')
