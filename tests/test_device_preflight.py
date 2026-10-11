# SPDX-License-Identifier: Apache-2.0
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from device_preflight import inspect, SIZES, MOUNTS


def fixture():
    values = {'getprop ro.product.device': 'dangol', 'getprop ro.product.manufacturer': 'NEXELL',
              'getprop ro.board.platform': 's5p6818', 'getprop ro.hardware': 'dangol', 'id -u': '0',
              'cat /sys/class/block/mmcblk0/size': '15269888',
              'cat /fstab.dangol': '\n'.join('/dev/block/mmcblk0p%d %s ext4 ro wait' % row for row in MOUNTS.items())}
    # Synthetic contiguous regions, not a claim of measured starts for p5-p9.
    start = 9600
    for part, size in SIZES.items():
        if part == 3:
            start = 142720
        values['cat /sys/class/block/mmcblk0p%d/start' % part] = str(start)
        values['cat /sys/class/block/mmcblk0p%d/size' % part] = str(size)
        start += size
    return values


class PreflightTests(unittest.TestCase):
    def test_supported_fixture(self):
        report = inspect(fixture().__getitem__)
        self.assertTrue(report['supported_identity_and_layout'])
        self.assertFalse(report['flash_authorized'])
    def test_identity_root_size_start_overlap(self):
        for key, value in [('getprop ro.hardware', 'other'), ('id -u', '2000'),
                           ('cat /sys/class/block/mmcblk0/size', '1'),
                           ('cat /sys/class/block/mmcblk0p1/start', '9601'),
                           ('cat /sys/class/block/mmcblk0p7/start', '9600')]:
            values = fixture()
            values[key] = value
            with self.assertRaises(ValueError):
                inspect(values.__getitem__)
    def test_fstab_redirect(self):
        values = fixture()
        values['cat /fstab.dangol'] = values['cat /fstab.dangol'].replace('mmcblk0p3', 'mmcblk0p5')
        with self.assertRaises(ValueError):
            inspect(values.__getitem__)
