# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_inspect_system import sparse, filesystem
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import expand_system as tool


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / 'source.img', self.root / 'new.raw.img'

    def invoke(self, data, size, apply=False):
        self.source.write_bytes(data)
        with patch.dict(tool.PARTITIONS, {'dangol': size}):
            return tool.expand(self.source, self.output, hashlib.sha256(data).hexdigest(), 'dangol', apply)

    def test_dry_run_no_output(self):
        data, expanded = sparse()
        result = self.invoke(data, len(expanded))
        self.assertFalse(result['applied'])
        self.assertFalse(self.output.exists())

    def test_sparse_zero_holes_and_readback(self):
        data, expanded = sparse()
        result = self.invoke(data, len(expanded), True)
        self.assertEqual(self.output.read_bytes(), expanded)
        self.assertTrue(result['host_output_checksum_verified'])
        self.assertEqual(result['sparse_holes_zeroed_bytes'], 4096)
        self.assertFalse(result['publication_approved'])

    def test_raw_copy(self):
        data = filesystem()
        self.invoke(data, len(data), True)
        self.assertEqual(self.output.read_bytes(), data)

    def test_existing_output_preserved(self):
        self.output.write_bytes(b'OWNER_FILE')
        with self.assertRaises(ValueError):
            self.invoke(filesystem(), 4096, True)
        self.assertEqual(self.output.read_bytes(), b'OWNER_FILE')

    def test_invalid_sparse_before_output_creation(self):
        data, expanded = sparse()
        with self.assertRaises(ValueError):
            self.invoke(data[:-1], len(expanded), True)
        self.assertFalse(self.output.exists())

    def test_wrong_checksum_before_output(self):
        self.source.write_bytes(filesystem())
        with self.assertRaises(ValueError):
            tool.expand(self.source, self.output, '0' * 64, 'acer-a1-840fhd', True)
        self.assertFalse(self.output.exists())
