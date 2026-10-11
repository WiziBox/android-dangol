# SPDX-License-Identifier: Apache-2.0
import struct
import zlib
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from check_boot_environment import inspect


def environment(command=None, extra=b''):
    command = command or b'mmc read 0x7107f800 0x2580 0xa6d8;dtimg load_mmc 0x20d80 0x7A000000 0; bootm 0x7107f800 723ac000 0x7A000000'
    payload = b'bootcmd=' + command + b'\0' + extra + b'\0'
    payload += bytes(16380 - len(payload))
    return struct.pack('<I', zlib.crc32(payload)) + payload


class EnvironmentTests(unittest.TestCase):
    def test_sufficient_and_insufficient(self):
        self.assertTrue(inspect(environment(), 21868544)['read_length_sufficient'])
        self.assertFalse(inspect(environment(
            b'mmc read 0x7107f800 0x2580 0xa348;dtimg load_mmc 0x20d80 0x7A000000 0; bootm 0x7107f800 723ac000 0x7A000000'), 21868544)['read_length_sufficient'])

    def test_bad_crc_and_size(self):
        for data in (b'', environment()[:-1], bytes(16384), environment()[:-1] + b'x'):
            with self.assertRaises(ValueError):
                inspect(data, 21868544)

    def test_duplicate_and_unknown_command(self):
        for data in (environment(extra=b'bootcmd=x\0'), environment(b'run arbitrary')):
            with self.assertRaises(ValueError):
                inspect(data, 21868544)

    def test_no_private_values_in_report(self):
        report = inspect(environment(extra=b'serial#=PRIVATE_OWNER\0ethaddr=PRIVATE_MAC\0'), 21868544)
        self.assertNotIn('PRIVATE', str(report))
        self.assertFalse(report['bootability_verified'])

    def test_invalid_boot_size(self):
        for size in (True, 0, 62914561):
            with self.assertRaises(ValueError):
                inspect(environment(), size)
