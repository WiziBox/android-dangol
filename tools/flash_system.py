#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guarded recovery root-ADB system streaming, dry-run by default. Never reboot."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from device_preflight import inspect as inspect_device
from inspect_system import inspect as inspect_image
from verify_backup import verify, PARTITIONS
from backup_device import device_hash

SYSTEM = '/dev/block/mmcblk0p3'
SIZE = 2147483648


def recovery_guard(read):
    inspect_device(read)
    if read('getprop ro.bootmode').strip() != 'recovery':
        raise ValueError('recovery required')
    if read('test -f /tmp/recovery.log && echo RECOVERY').strip() != 'RECOVERY':
        raise ValueError('recovery marker required')
    if read('cat /sys/class/block/mmcblk0p3/dev').strip() != '179:3':
        raise ValueError('unsupported system block identity')
    if read('readlink -f ' + SYSTEM).strip() != SYSTEM:
        raise ValueError('redirected system node')
    mounts = read('cat /proc/self/mountinfo')
    if not mounts.strip():
        raise ValueError('missing mount inventory')
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 10 or '-' not in fields:
            raise ValueError('unsupported mount inventory')
        if fields[2] == '179:3' or fields[4] == '/system' or fields[4].startswith('/system/'):
            raise ValueError('system still mounted')


def owner_backup(directory, serial):
    records = []
    for name in ('backup-receipt.json', 'owner-device-record.json'):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
            raise ValueError('missing owner backup records')
        records.append(json.loads(path.read_text(encoding='utf-8')))
    receipt, record = records
    if (not isinstance(receipt, dict) or not isinstance(record, dict) or record.get('schema') != 1 or record.get('device') != 'dangol'
            or record.get('serial') != serial or record.get('files') != receipt.get('files')):
        raise ValueError('backup is not bound to selected owner serial')
    verify(directory, receipt)


def digest(stream):
    stream.seek(0)
    hashed = hashlib.sha256()
    for data in iter(lambda: stream.read(1048576), b''):
        hashed.update(data)
    return hashed.hexdigest()


def install(read, write, source, expected, backup_dir, serial, apply=False):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('invalid source SHA-256')
    if source.is_symlink() or not source.is_file() or source.stat().st_size != SIZE:
        raise ValueError('full raw system file required')
    owner_backup(backup_dir, serial)
    recovery_guard(read)
    with source.open('rb') as stream:
        if digest(stream) != expected:
            raise ValueError('source SHA-256 mismatch')
        stream.seek(0)
        checked = inspect_image(stream, SIZE)
        if checked['format'] != 'raw':
            raise ValueError('sparse source must first be expanded on host')
        report = {'dry_run': not apply, 'device_written': False,
                  'system_bytes': SIZE, 'owner_backup_checked': True,
                  'system_readback_verified': False, 'boot_or_environment_written': False,
                  'rebooted': False, 'restore_proven': False}
        if not apply:
            return report
        recovery_guard(read)
        if digest(stream) != expected:
            raise ValueError('source changed before write')
        stream.seek(0)
        write('dd of=' + SYSTEM + ' bs=1048576', stream)
        read('sync')
        if device_hash(read, SYSTEM) != expected:
            raise ValueError('system readback differs; do not reboot')
        recovery_guard(read)
        if digest(stream) != expected:
            raise ValueError('host source changed during operation')
        report['device_written'] = True
        report['system_readback_verified'] = True
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--owner-backup-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='overwrite only system; requires onsite recovery')
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
        def write(command, stream):
            subprocess.run([args.adb, '-s', args.serial, 'exec-in', command], stdin=stream,
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        print(json.dumps(install(read, write, args.image, args.sha256,
                                 args.owner_backup_dir, args.serial, args.apply), indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, subprocess.SubprocessError):
        print(json.dumps({'error': 'system install refused or failed; may be partially written; do not reboot',
                          'automatic_retry': False, 'restore_proven': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
