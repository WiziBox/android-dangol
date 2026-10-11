#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guarded Dangol recovery boot/environment installation. Dry-run; no reboot."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import struct
import zlib
from audit_boot import audit_bytes
from pack_boot import components
from flash_system import owner_backup, recovery_guard
from backup_device import device_hash
from extract_boot_environment import extract, PREBOOT_BYTES, ENV_OFFSET, ENV_BYTES
from prepare_boot_environment import prepare

BOOT_BYTES = 62914560
PREBOOT_READ = 'dd if=/dev/block/mmcblk0 bs=512 count=9600'
ENV_READ = 'dd if=/dev/block/mmcblk0 bs=512 skip=5889 count=32'
BOOT_WRITE = 'dd of=/dev/block/mmcblk0p1 bs=1048576'
ENV_WRITE = 'dd of=/dev/block/mmcblk0 bs=512 seek=5889 conv=notrunc'


def private_file(path, maximum):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError('unsupported private input')
    return path.read_bytes()


def install(read, capture, write, source, expected, backup_dir, serial, apply=False):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('invalid boot SHA-256')
    owner_backup(backup_dir, serial)
    record = json.loads(private_file(backup_dir / 'owner-device-record.json', 16384))
    preboot_record = record.get('preboot')
    if (not isinstance(preboot_record, dict) or preboot_record.get('bytes') != PREBOOT_BYTES
            or not isinstance(preboot_record.get('sha256'), str)):
        raise ValueError('verified private preboot backup required')
    preboot = private_file(backup_dir / 'dangol-preboot.bin', PREBOOT_BYTES)
    image = private_file(source, BOOT_BYTES)
    if hashlib.sha256(image).hexdigest() != expected:
        raise ValueError('boot source SHA-256 mismatch')
    original_boot = private_file(backup_dir / 'dangol-boot.img', BOOT_BYTES)
    if components(image) != components(original_boot):
        raise ValueError('owner kernel/DTB pairing differs')
    audit = audit_bytes(image, 'dangol')
    if audit['findings']:
        raise ValueError('new boot key/policy audit refused')
    environment, report = extract(preboot, preboot_record['sha256'], image)
    candidate, changed = prepare(environment, report['required_read_sectors'] * 512)
    recovery_guard(read)
    if read('cat /sys/class/block/mmcblk0/dev').strip() != '179:0' or read('readlink -f /dev/block/mmcblk0').strip() != '/dev/block/mmcblk0':
        raise ValueError('redirected parent disk')
    if read('cat /sys/class/block/mmcblk0p1/dev').strip() != '179:1':
        raise ValueError('unsupported boot block identity')
    if read('readlink -f /dev/block/mmcblk0p1').strip() != '/dev/block/mmcblk0p1':
        raise ValueError('redirected boot node')
    def unmounted_boot():
        for row in read('cat /proc/self/mountinfo').splitlines():
            fields = row.split()
            if len(fields) < 10 or '-' not in fields:
                raise ValueError('unsupported mounts')
            if fields[2] == '179:1':
                raise ValueError('boot mounted')
    unmounted_boot()
    if capture(PREBOOT_READ, PREBOOT_BYTES) != preboot:
        raise ValueError('live preboot no longer equals owner backup')
    result = {'dry_run': not apply, 'boot_written_and_readback_verified': False,
              'environment_change_needed': changed, 'environment_written_and_readback_verified': False,
              'other_environment_values_preserved': True, 'rebooted': False,
              'bootability_verified': False, 'restore_proven': False}
    if not apply:
        return result
    recovery_guard(read)
    unmounted_boot()
    if capture(ENV_READ, ENV_BYTES) != environment:
        raise ValueError('live environment changed before boot write')
    padded = image + bytes(BOOT_BYTES - len(image))
    write(BOOT_WRITE, padded)
    read('sync')
    if device_hash(read, '/dev/block/mmcblk0p1') != hashlib.sha256(padded).hexdigest():
        raise ValueError('boot readback differs; do not reboot')
    result['boot_written_and_readback_verified'] = True
    recovery_guard(read)
    if capture(PREBOOT_READ, PREBOOT_BYTES) != preboot:
        raise ValueError('preboot changed after boot write; do not reboot')
    if changed:
        write(ENV_WRITE, candidate)
        read('sync')
        if capture(ENV_READ, ENV_BYTES) != candidate:
            raise ValueError('environment readback differs; do not reboot')
        final_preboot = capture(PREBOOT_READ, PREBOOT_BYTES)
        expected_preboot = preboot[:ENV_OFFSET] + candidate + preboot[ENV_OFFSET + ENV_BYTES:]
        if final_preboot != expected_preboot:
            raise ValueError('unexpected preboot byte changes; do not reboot')
        result['environment_written_and_readback_verified'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--owner-backup-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-onsite-recovery', action='store_true')
    args = parser.parse_args()
    try:
        if (not args.serial or args.serial.startswith('-') or any(ord(c) < 33 for c in args.serial)
                or args.apply and not args.confirm_onsite_recovery):
            raise ValueError('explicit serial and onsite recovery confirmation required')
        def read(command):
            result = subprocess.run([args.adb, '-s', args.serial, 'shell', command],
                                    check=True, capture_output=True, timeout=300)
            if len(result.stdout) > 65536:
                raise ValueError('oversized response')
            return result.stdout.decode('ascii')
        def capture(command, size):
            result = subprocess.run([args.adb, '-s', args.serial, 'exec-out', command],
                                    check=True, capture_output=True, timeout=60)
            if len(result.stdout) != size:
                raise ValueError('short device capture')
            return result.stdout
        def write(command, data):
            with tempfile.TemporaryFile() as stream:
                stream.write(data)
                stream.seek(0)
                subprocess.run([args.adb, '-s', args.serial, 'exec-in', command], stdin=stream,
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        print(json.dumps(install(read, capture, write, args.image, args.sha256,
                                 args.owner_backup_dir, args.serial, args.apply), indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, EOFError, struct.error, zlib.error, subprocess.SubprocessError):
        print(json.dumps({'error': 'boot/environment install refused or failed; may be partially written; do not reboot',
                          'automatic_retry': False, 'restore_proven': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
