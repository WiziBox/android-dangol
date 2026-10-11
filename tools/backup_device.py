#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read selected Dangol partitions into a new private host directory. No device writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from device_preflight import inspect
from verify_backup import PARTITIONS, inventory

BLOCKS = {'dangol-boot.img': 1, 'dangol-p2.img': 2, 'dangol-system.img': 3,
          'dangol-p5.img': 5, 'dangol-recovery.img': 7, 'dangol-misc.img': 8}
PREBOOT_BYTES = 4915200
PREBOOT_READ = 'dd if=/dev/block/mmcblk0 bs=512 count=9600'


def capture_preboot(read, capture, output):
    def checksum():
        result = read(PREBOOT_READ + ' 2>/dev/null | sha256sum').strip()
        match = re.fullmatch(r'([0-9a-f]{64})\s+\*?-', result)
        if not match:
            raise ValueError('unsupported preboot hash response')
        return match[1]
    before = checksum()
    path = output / 'dangol-preboot.bin'
    with path.open('xb') as stream:
        path.chmod(0o600)
        capture(PREBOOT_READ, stream)
    if path.stat().st_size != PREBOOT_BYTES:
        raise ValueError('short preboot backup')
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != actual or checksum() != actual:
        raise ValueError('preboot changed or capture differs')
    return {'bytes': PREBOOT_BYTES, 'sha256': actual}


def require_read_only_mounts(text):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 10 or '-' not in fields:
            raise ValueError('unsupported mount inventory')
        if fields[2] in {'179:1', '179:2', '179:3', '179:5', '179:7', '259:0'}:
            if 'rw' in fields[5].split(','):
                raise ValueError('backup target mounted writable')


def device_hash(read, block):
    response = read('sha256sum ' + block).strip()
    match = re.fullmatch(r'([0-9a-f]{64})\s+\*?' + re.escape(block), response)
    if not match:
        raise ValueError('unsupported device hash response')
    return match[1]


def backup(read, capture, output, serial, apply=False):
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('new private output directory required')
    repo = Path(__file__).resolve().parents[1]
    if repo == output.resolve() or repo in output.resolve().parents:
        raise ValueError('output must stay outside publication repository')
    inspect(read)
    require_read_only_mounts(read('cat /proc/self/mountinfo'))
    expected = {1: '179:1', 2: '179:2', 3: '179:3', 5: '179:5', 7: '179:7', 8: '259:0'}
    for number, dev in expected.items():
        if read('cat /sys/class/block/mmcblk0p%d/dev' % number).strip() != dev:
            raise ValueError('unsupported block identity')
    if not apply:
        return {'dry_run': True, 'partition_files_planned': 6, 'device_writes': False,
                'backup_created': False, 'restore_proven': False}
    import shutil
    if shutil.disk_usage(output.parent).free < sum(PARTITIONS.values()) + PREBOOT_BYTES + 16777216:
        raise ValueError('insufficient host space')
    output.mkdir(mode=0o700)
    preboot = capture_preboot(read, capture, output)
    rows = {}
    for name, number in BLOCKS.items():
        block = '/dev/block/mmcblk0p%d' % number
        require_read_only_mounts(read('cat /proc/self/mountinfo'))
        before = device_hash(read, block)
        path = output / name
        with path.open('xb') as stream:
            path.chmod(0o600)
            capture('dd if=' + block + ' bs=1048576', stream)
        if path.stat().st_size != PARTITIONS[name]:
            raise ValueError('short backup capture')
        hashed = hashlib.sha256()
        with path.open('rb') as stream:
            for data in iter(lambda: stream.read(1048576), b''):
                hashed.update(data)
        after = device_hash(read, block)
        if before != after or after != hashed.hexdigest():
            raise ValueError('device changed or host capture differs')
        rows[name] = {'bytes': PARTITIONS[name], 'sha256': after}
    inspect(read)
    require_read_only_mounts(read('cat /proc/self/mountinfo'))
    if inventory(output) != rows:
        raise ValueError('final host inventory differs')
    final_preboot_hash = read(PREBOOT_READ + ' 2>/dev/null | sha256sum').strip()
    if not re.fullmatch(preboot['sha256'] + r'\s+\*?-', final_preboot_hash):
        raise ValueError('preboot changed after partition backup')
    preboot_path = output / 'dangol-preboot.bin'
    if preboot_path.stat().st_size != PREBOOT_BYTES or hashlib.sha256(preboot_path.read_bytes()).hexdigest() != preboot['sha256']:
        raise ValueError('host preboot changed after capture')
    records = {
        'backup-receipt.json': {'schema': 1, 'device': 'dangol', 'files': rows},
        'owner-device-record.json': {'schema': 1, 'device': 'dangol', 'serial': serial,
                                    'files': rows, 'preboot': preboot, 'factory_original_proven': False,
                                    'whole_disk_backup': False, 'restore_proven': False},
    }
    for name, record in records.items():
        path = output / name
        with path.open('x', encoding='utf-8') as stream:
            path.chmod(0o600)
            json.dump(record, stream, indent=2)
    return {'dry_run': False, 'partition_files_verified': 6, 'backup_created': True,
            'device_writes': False, 'private_serial_not_printed': True,
            'preboot_backup_verified': True, 'whole_disk_backup': False, 'restore_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='read device partitions and write new host backups')
    args = parser.parse_args()
    try:
        if not args.serial or args.serial.startswith('-') or any(ord(c) < 33 for c in args.serial):
            raise ValueError('invalid serial')
        def read(command):
            result = subprocess.run([args.adb, '-s', args.serial, 'shell', command],
                                    check=True, capture_output=True, timeout=300)
            if len(result.stdout) > 65536:
                raise ValueError('oversized response')
            return result.stdout.decode('ascii')
        def capture(command, stream):
            subprocess.run([args.adb, '-s', args.serial, 'exec-out', command],
                           check=True, stdout=stream, stderr=subprocess.PIPE, timeout=600)
        print(json.dumps(backup(read, capture, args.output, args.serial, args.apply), indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print(json.dumps({'error': 'backup refused or incomplete; preserve private partial output',
                          'device_writes': False, 'restore_proven': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
