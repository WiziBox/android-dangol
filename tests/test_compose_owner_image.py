# SPDX-License-Identifier: Apache-2.0
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import compose_owner_image as tool

CAL = b'boardtype=0x5ef\nboardrev=0x1100\nsromrev=9\nmacaddr=02:00:00:00:00:01\n'


class OwnerComposeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.cal, self.output = (self.root / name for name in ('base.img', 'owner.cal', 'new.img'))
        data = bytearray(4096)
        data[1080:1082] = b'\x53\xef'
        self.source.write_bytes(data)
        self.cal.write_bytes(CAL)
        self.expected = hashlib.sha256(data).hexdigest()
        self.target = tool.PROFILES['acer-a1-840fhd'][1]
        profiles = patch.dict(tool.PROFILES, {'acer-a1-840fhd': (4096, self.target)})
        profiles.start()
        self.addCleanup(profiles.stop)
        checker = patch.object(tool, 'filesystem_check')
        checker.start()
        self.addCleanup(checker.stop)
        reader = patch.object(tool, 'fs_read', side_effect=self.read)
        reader.start()
        self.addCleanup(reader.stop)
        temporary_path_check = patch.object(tool, 'require_temp_path')
        temporary_path_check.start()
        self.addCleanup(temporary_path_check.stop)
    def read(self, image, command):
        if command in ('stat /vendor', 'stat /vendor/firmware'):
            return b'Type: directory', b''
        if command == 'stat ' + self.target:
            if image == self.source:
                return b'', b'File not found'
            return b'Type: regular Mode: 0644 User: 0 Group: 0', b''
        if command == 'cat ' + self.target:
            return CAL, b''
        if command == 'ea_get ' + self.target + ' security.selinux':
            return b'security.selinux = "u:object_r:vendor_file:s0\\000"', b''
        raise AssertionError('unexpected command')
    def invoke(self, apply=False, confirm=False):
        return tool.compose(self.source, self.cal, self.output, self.expected,
                            'acer-a1-840fhd', apply, confirm)
    def test_dry_no_output(self):
        self.assertTrue(self.invoke()['dry_run'])
        self.assertFalse(self.output.exists())
    def test_apply_new_private_output_no_device(self):
        with patch.object(tool.subprocess, 'run') as runner:
            result = self.invoke(True, True)
        self.assertTrue(result['calibration_readback_verified'])
        self.assertTrue(result['base_unchanged'])
        self.assertFalse(result['publication_approved'])
        self.assertEqual(runner.call_count, 5)
        self.assertTrue(all(call.args[0][0] == 'debugfs' for call in runner.call_args_list))
        self.assertNotIn('02:00:00', json.dumps(result))
    def test_owner_confirmation_required(self):
        with self.assertRaises(ValueError):
            self.invoke(True)
        self.assertFalse(self.output.exists())
    def test_existing_output_preserved(self):
        self.output.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            self.invoke(True, True)
        self.assertEqual(self.output.read_bytes(), b'keep')
    def test_bad_hash_and_sparse_refused(self):
        self.expected = '0' * 64
        with self.assertRaises(ValueError):
            self.invoke(True, True)
        self.source.write_bytes(bytes(4096))
        with self.assertRaises(ValueError):
            self.invoke(True, True)
        self.assertFalse(self.output.exists())
    def test_credentials_rejected(self):
        for extra in (b'psk=PRIVATE_FIXTURE', b'SSID=PRIVATE_FIXTURE', b'network={',
                      b'key=-----BEGIN RSA PRIVATE KEY-----'):
            with self.assertRaises(ValueError):
                tool.validate_calibration(CAL + extra + b'\n', 'acer-a1-840fhd')
    def test_dangol_profile_and_wrong_board(self):
        self.assertEqual(tool.validate_calibration(CAL, 'dangol'), CAL)
        with self.assertRaises(ValueError):
            tool.validate_calibration(CAL.replace(b'0x5ef', b'0xffff'), 'acer-a1-840fhd')
    def test_readback_mismatch_preserves_partial(self):
        reader = self.read
        with patch.object(tool.subprocess, 'run'), patch.object(tool, 'fs_read', side_effect=lambda image, command: (b'WRONG', b'') if command.startswith('cat ') else reader(image, command)):
            with self.assertRaises(ValueError):
                self.invoke(True, True)
        self.assertTrue(self.output.exists())
    def test_cli_failure_does_not_print_private_inputs(self):
        self.cal.write_bytes(CAL + b'password=PRIVATE_FIXTURE\n')
        captured = io.StringIO()
        with patch.object(tool.sys, 'platform', 'linux'), contextlib.redirect_stdout(captured):
            result = tool.main(['--device', 'acer-a1-840fhd', '--input', str(self.source),
                                '--calibration', str(self.cal), '--output', str(self.output),
                                '--base-sha256', self.expected])
        self.assertEqual(result, 2)
        self.assertNotIn('PRIVATE_FIXTURE', captured.getvalue())
        self.assertNotIn(str(self.root), captured.getvalue())
