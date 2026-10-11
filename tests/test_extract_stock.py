# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
try:
    spec = importlib.util.spec_from_file_location('dangol_extract', ROOT / 'tools/extract_stock.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
finally:
    sys.path.pop(0)


class ExtractTests(unittest.TestCase):
    def test_regular_file_read_only(self):
        replies = [subprocess.CompletedProcess([], 0, b'Type: regular Size: 7', b''),
                   subprocess.CompletedProcess([], 0, b'FIXTURE', b'')]
        with patch.object(tool.subprocess, 'run', side_effect=replies) as run:
            self.assertEqual(tool.read_ext4(Path('owner.img'), 'lib/test.so'), b'FIXTURE')
        for call in run.call_args_list:
            self.assertNotIn('-w', call.args[0])
            self.assertNotIn('shell', call.kwargs)

    def test_relative_symlink_in_image(self):
        replies = [subprocess.CompletedProcess([], 0, b'Type: symlink Fast link dest: "fw.bin"', b''),
                   subprocess.CompletedProcess([], 0, b'Type: regular Size: 7', b''),
                   subprocess.CompletedProcess([], 0, b'FIXTURE', b'')]
        with patch.object(tool.subprocess, 'run', side_effect=replies) as run:
            self.assertEqual(tool.read_ext4(Path('owner.img'), 'vendor/firmware/link.bin'), b'FIXTURE')
        self.assertEqual(run.call_args_list[1].args[0][2], 'stat /vendor/firmware/fw.bin')

    def test_symlink_loop_refused(self):
        reply = subprocess.CompletedProcess([], 0, b'Type: symlink Fast link dest: "loop"', b'')
        with patch.object(tool.subprocess, 'run', return_value=reply), self.assertRaises(ValueError):
            tool.read_ext4(Path('owner.img'), 'loop')

    def test_short_read_refused(self):
        replies = [subprocess.CompletedProcess([], 0, b'Type: regular Size: 7', b''),
                   subprocess.CompletedProcess([], 0, b'SHORT', b'')]
        with patch.object(tool.subprocess, 'run', side_effect=replies), self.assertRaises(ValueError):
            tool.read_ext4(Path('owner.img'), 'lib/test.so')

    def test_non_ext4_refused_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'owner.img'
            image.write_bytes(b'not ext4')
            output = Path(folder) / 'new'
            index = {'schema': 1, 'device': 'dangol', 'owner_calibration': tool.CALIBRATION}
            with self.assertRaises(ValueError):
                tool.extract(index, image, output)
            self.assertFalse(output.exists())
