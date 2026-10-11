# SPDX-License-Identifier: Apache-2.0
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import verify_backup as tool


class BackupTests(unittest.TestCase):
    def test_round_trip_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch.dict(tool.PARTITIONS, {'test.img': 4}, clear=True):
                (directory / 'test.img').write_bytes(b'abcd')
                receipt = {'schema': 1, 'device': 'dangol', 'files': tool.inventory(directory)}
                tool.verify(directory, receipt)
                (directory / 'test.img').write_bytes(b'efgh')
                with self.assertRaises(ValueError):
                    tool.verify(directory, receipt)

    def test_missing_and_short_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch.dict(tool.PARTITIONS, {'test.img': 4}, clear=True):
                with self.assertRaises(ValueError):
                    tool.inventory(directory)
                (directory / 'test.img').write_bytes(b'a')
                with self.assertRaises(ValueError):
                    tool.inventory(directory)

    def test_malformed_receipts(self):
        for receipt in ([], {}, {'schema': 1, 'device': 'other', 'files': {}},
                        {'schema': 1, 'device': 'dangol', 'files': {}},
                        {'schema': 1, 'device': 'dangol', 'files': [], 'extra': 1}):
            with self.assertRaises(ValueError):
                tool.verify(Path('.'), receipt)


if __name__ == '__main__':
    unittest.main()
