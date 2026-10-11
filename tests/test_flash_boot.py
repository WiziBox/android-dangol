# SPDX-License-Identifier: Apache-2.0
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_pack_boot import fixture, module
from test_audit_boot import archive
from test_check_boot_environment import environment
import flash_boot as tool


class BootFlashTests(unittest.TestCase):
    def invoke(self, apply=False, bad_boot_readback=False, bad_prefix=False):
        self.writes = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = fixture()
            ramdisk = gzip.compress(archive([('default.prop', b'ro.secure=1\nro.adb.secure=1\n')]), mtime=0)
            image, _ = module.pack(old, ramdisk)
            source = root / 'new-boot.img'
            source.write_bytes(image)
            (root / 'dangol-boot.img').write_bytes(old)
            command = b'mmc read 0x7107f800 0x2580 0x0001;dtimg load_mmc 0x20d80 0x7A000000 0; bootm 0x7107f800 723ac000 0x7A000000'
            env = environment(command, b'serial#=PRIVATE\0')
            preboot = bytearray(tool.PREBOOT_BYTES)
            preboot[tool.ENV_OFFSET:tool.ENV_OFFSET + tool.ENV_BYTES] = env
            original = bytes(preboot)
            (root / 'dangol-preboot.bin').write_bytes(original)
            (root / 'owner-device-record.json').write_text(json.dumps({'preboot':{'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}}))
            state = {'preboot':original, 'boot':b''}
            def read(cmd):
                values = {'cat /sys/class/block/mmcblk0p1/dev':'179:1',
                          'cat /sys/class/block/mmcblk0/dev':'179:0',
                          'readlink -f /dev/block/mmcblk0':'/dev/block/mmcblk0',
                          'readlink -f /dev/block/mmcblk0p1':'/dev/block/mmcblk0p1',
                          'cat /proc/self/mountinfo':'1 0 0:1 / /tmp rw - tmpfs tmpfs rw', 'sync':''}
                if cmd.startswith('sha256sum '):
                    sha = '0' * 64 if bad_boot_readback else hashlib.sha256(state['boot']).hexdigest()
                    return sha + '  /dev/block/mmcblk0p1'
                return values[cmd]
            def capture(cmd, size):
                if cmd == tool.PREBOOT_READ:
                    return b'invalid' if bad_prefix else state['preboot']
                return state['preboot'][tool.ENV_OFFSET:tool.ENV_OFFSET + tool.ENV_BYTES]
            def write(cmd, data):
                self.writes.append((cmd, data))
                if cmd == tool.BOOT_WRITE:
                    state['boot'] = data
                else:
                    state['preboot'] = state['preboot'][:tool.ENV_OFFSET] + data + state['preboot'][tool.ENV_OFFSET + tool.ENV_BYTES:]
            with patch.object(tool, 'owner_backup'), patch.object(tool, 'recovery_guard'), patch.object(tool, 'BOOT_BYTES', 16384):
                result = tool.install(read, capture, write, source, hashlib.sha256(image).hexdigest(), root, 'PRIVATE', apply)
            return result, state, original
    def test_dry_run_no_writes(self):
        result, _, _ = self.invoke()
        self.assertTrue(result['environment_change_needed'])
        self.assertFalse(result['boot_written_and_readback_verified'])
        self.assertEqual(self.writes, [])
    def test_boot_then_exact_environment_only(self):
        result, state, original = self.invoke(True)
        self.assertEqual([cmd for cmd, _ in self.writes], [tool.BOOT_WRITE, tool.ENV_WRITE])
        self.assertEqual(len(self.writes[0][1]), 16384)
        self.assertEqual(len(self.writes[1][1]), tool.ENV_BYTES)
        self.assertEqual(state['preboot'][:tool.ENV_OFFSET], original[:tool.ENV_OFFSET])
        self.assertEqual(state['preboot'][tool.ENV_OFFSET + tool.ENV_BYTES:], original[tool.ENV_OFFSET + tool.ENV_BYTES:])
        self.assertTrue(result['environment_written_and_readback_verified'])
        self.assertFalse(result['rebooted'])
        self.assertNotIn('PRIVATE', str(result))
    def test_boot_readback_failure_never_writes_environment(self):
        with self.assertRaises(ValueError):
            self.invoke(True, bad_boot_readback=True)
        self.assertEqual([cmd for cmd, _ in self.writes], [tool.BOOT_WRITE])
    def test_foreign_or_changed_preboot_no_writes(self):
        with self.assertRaises(ValueError):
            self.invoke(True, bad_prefix=True)
        self.assertEqual(self.writes, [])
