# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest
from test_check_boot_environment import environment
from test_pack_boot import fixture
import extract_boot_environment as tool


class ExtractionTests(unittest.TestCase):
    def source(self):
        data = bytearray(tool.PREBOOT_BYTES)
        data[tool.ENV_OFFSET:tool.ENV_OFFSET + tool.ENV_BYTES] = environment(extra=b'serial#=PRIVATE_OWNER\0')
        return bytes(data)
    def test_exact_environment_and_no_private_report_values(self):
        source = self.source()
        extracted, report = tool.extract(source, hashlib.sha256(source).hexdigest(), fixture())
        self.assertEqual(extracted, source[tool.ENV_OFFSET:tool.ENV_OFFSET + tool.ENV_BYTES])
        self.assertNotIn('PRIVATE_OWNER', str(report))
        self.assertTrue(report['environment_crc_valid'])
        self.assertFalse(report['publication_approved'])
    def test_bad_hash_and_missing_region(self):
        source = self.source()
        for data, sha in ((source, '0' * 64), (source[:-1], hashlib.sha256(source[:-1]).hexdigest())):
            with self.assertRaises(ValueError):
                tool.extract(data, sha, fixture())
    def test_corrupt_crc_and_unsupported_boot(self):
        data = bytearray(self.source())
        data[tool.ENV_OFFSET] ^= 1
        with self.assertRaises(ValueError):
            tool.extract(bytes(data), hashlib.sha256(data).hexdigest(), fixture())
        source = self.source()
        with self.assertRaises(ValueError):
            tool.extract(source, hashlib.sha256(source).hexdigest(), b'not-boot')
