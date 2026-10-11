#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only root-ADB Dangol layout inspection; no reboot, root enable or writes."""
import argparse
import json
import re
import subprocess
import sys

SIZES = {1: 122880, 2: 6144, 3: 4194304, 5: 131072,
         6: 1048576, 7: 131072, 8: 2048, 9: 9609856}
MOUNTS = {1: '/boot', 3: '/system', 6: '/cache', 7: '/recovery', 8: '/misc', 9: '/data'}


def inspect(read):
    expected = {'ro.product.device': 'dangol', 'ro.product.manufacturer': 'NEXELL',
                'ro.board.platform': 's5p6818', 'ro.hardware': 'dangol'}
    for prop, value in expected.items():
        if read('getprop ' + prop).strip() != value:
            raise ValueError('unsupported identity')
    if read('id -u').strip() != '0':
        raise ValueError('existing root ADB required')
    fstab = read('cat /fstab.dangol')
    mappings = {}
    for line in fstab.splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        if len(fields) < 2:
            raise ValueError('invalid fstab')
        if fields[1] in MOUNTS.values():
            if fields[1] in mappings:
                raise ValueError('duplicate mount mapping')
            mappings[fields[1]] = fields[0]
    if mappings != {mount: '/dev/block/mmcblk0p%d' % number for number, mount in MOUNTS.items()}:
        raise ValueError('unsupported mount mapping')
    def number(command):
        value = read(command).strip()
        if not re.fullmatch('[0-9]{1,12}', value):
            raise ValueError('invalid block geometry')
        return int(value)
    disk = number('cat /sys/class/block/mmcblk0/size')
    if disk != 15269888:
        raise ValueError('unsupported disk size')
    regions = []
    for partition, size in SIZES.items():
        base = '/sys/class/block/mmcblk0p%d/' % partition
        start = number('cat ' + base + 'start')
        actual = number('cat ' + base + 'size')
        if actual != size or start < 1 or start + size > disk:
            raise ValueError('unsupported partition size or bounds')
        if partition in (1, 3) and start != {1: 9600, 3: 142720}[partition]:
            raise ValueError('unsupported measured partition start')
        regions.append((start, start + size))
    regions.sort()
    if any(left[1] > right[0] for left, right in zip(regions, regions[1:])):
        raise ValueError('partition overlap')
    return {'supported_identity_and_layout': True, 'partition_regions_checked': len(regions),
            'existing_root_confirmed': True, 'device_writes': False,
            'serial_not_printed': True, 'recovery_mode_or_unmounted_system_verified': False,
            'boot_environment_and_backup_verified': False, 'flash_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()
    try:
        if not args.serial or args.serial.startswith('-') or any(ord(c) < 33 for c in args.serial):
            raise ValueError('invalid serial')
        def read(command):
            result = subprocess.run([args.adb, '-s', args.serial, 'shell', command],
                                    check=True, capture_output=True, timeout=10)
            if len(result.stdout) > 16384:
                raise ValueError('oversized response')
            return result.stdout.decode('ascii')
        print(json.dumps(inspect(read), indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print(json.dumps({'error': 'read-only Dangol preflight refused', 'device_writes': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
