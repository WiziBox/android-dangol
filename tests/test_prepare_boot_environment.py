# SPDX-License-Identifier: Apache-2.0
import unittest
from test_check_boot_environment import environment
from prepare_boot_environment import prepare
from check_boot_environment import inspect


class PrepareTests(unittest.TestCase):
    def test_preserves_sufficient_environment(self):
        source = environment()
        result, changed = prepare(source, 21864448)
        self.assertEqual(result, source)
        self.assertFalse(changed)

    def test_changes_only_count_and_crc(self):
        command = b'mmc read 0x7107f800 0x2580 0xa348;dtimg load_mmc 0x20d80 0x7A000000 0; bootm 0x7107f800 723ac000 0x7A000000'
        source = environment(command, b'serial#=PRIVATE\0other=0xa348\0')
        result, changed = prepare(source, 21864448)
        self.assertTrue(changed)
        self.assertEqual(result[4:], source[4:].replace(b'0xa348;', b'0xa6d0;', 1))
        self.assertTrue(inspect(result, 21864448)['read_length_sufficient'])
        self.assertIn(b'other=0xa348', result)

    def test_bad_crc_refused(self):
        with self.assertRaises(ValueError):
            prepare(bytes(16384), 21864448)
