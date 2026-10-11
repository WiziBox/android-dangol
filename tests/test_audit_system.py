# SPDX-License-Identifier: Apache-2.0
import base64
import io
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
try:
    import audit_system as tool
finally:
    sys.path.pop(0)


class SystemAuditTests(unittest.TestCase):
    def test_listing_actual_e2fsprogs_format(self):
        rows = tool.directory_entries(b'/2/040755/0/0/.//\n/2/040755/0/0/..//\n/496/100644/0/0/build.prop/2349/\n')
        self.assertEqual(rows, [('build.prop', 0o100644, 2349)])

    def test_owner_values_never_returned(self):
        secret = b'macaddr=02:11:22:33:44:55\npsk=PRIVATE_FIXTURE\n'
        findings = tool.findings('vendor/firmware/device.cal', secret)
        self.assertTrue(findings)
        self.assertNotIn('PRIVATE_FIXTURE', str(findings))
        self.assertNotIn('02:11:22', str(findings))

    def test_adb_approval_and_signing_files(self):
        key = base64.b64encode(struct.pack('<I', 64) + bytes(520))
        self.assertTrue(tool.findings('etc/unknown.bin', key))
        self.assertTrue(tool.findings('etc/adbkey', b''))
        self.assertTrue(tool.findings('etc/platform.pk8', b''))

    def test_private_pem_and_marker_only_distinct(self):
        self.assertTrue(tool.findings('unknown', b'-----BEGIN RSA PRIVATE KEY-----\nAQID\n-----END RSA PRIVATE KEY-----'))
        self.assertFalse(tool.findings('unknown', b'-----BEGIN RSA PRIVATE KEY-----'))

    def test_insecure_policy(self):
        self.assertTrue(tool.findings('etc/init/example.rc', b'setprop service.adb.tcp.port 5555\n'))
        self.assertTrue(tool.findings('build.prop', b'ro.adb.secure=0\n'))
        self.assertFalse(tool.findings('build.prop', b'ro.adb.secure=1\nservice.adb.tcp.port=-1\n'))

    def test_compressed_apk_member_scan_no_extraction(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('assets/adbkey', b'PRIVATE_FIXTURE')
        result = tool.scan_file('app/Test.apk', buffer.getvalue())
        self.assertEqual(result[0]['entry'], 'app/Test.apk!assets/adbkey')
        self.assertNotIn('PRIVATE_FIXTURE', str(result))

    def test_path_traversal_and_bad_listing_refused(self):
        for name in ('../escape', '/absolute', 'a/../b', 'a b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                tool.safe_path(name)
        with self.assertRaises(ValueError):
            tool.directory_entries(b'NOT A DIRECTORY INVENTORY')

    def test_android_compiled_resource_member_names(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('res/drawable/$avd_show_password__0.xml', b'NONSECRET_FIXTURE')
        self.assertFalse(tool.scan_file('app/Test.apk', buffer.getvalue()))

    def test_archive_traversal_refused_without_extraction(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../escape', b'FIXTURE')
        with self.assertRaises(ValueError):
            tool.scan_file('app/Test.apk', buffer.getvalue())

    def test_mock_image_scan_and_private_report(self):
        replies = [b'/2/040755/0/0/.//\n/20/100644/0/0/build.prop/17/\n', b'ro.adb.secure=1\n\n']
        with patch.object(tool, 'debugfs', side_effect=replies):
            report = tool.scan_image(Path('synthetic.img'))
        self.assertEqual(report['regular_files_scanned'], 1)
        self.assertTrue(report['limited_privacy_inventory_passed'])
        self.assertFalse(report['publication_approved'])

    def test_empty_inventory_is_not_a_pass(self):
        with patch.object(tool, 'debugfs', return_value=b'/2/040755/0/0/.//\n'), self.assertRaises(ValueError):
            tool.scan_image(Path('synthetic.img'))

    def test_fscheck_never_requests_repair(self):
        with patch.object(tool.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(tool.check_filesystem(Path('synthetic.img')))
        self.assertEqual(run.call_args.args[0], ['e2fsck', '-f', '-n', 'synthetic.img'])

    def test_fscheck_error_is_not_success(self):
        with patch.object(tool.subprocess, 'run', return_value=subprocess.CompletedProcess([], 4)), self.assertRaises(ValueError):
            tool.check_filesystem(Path('synthetic.img'))
