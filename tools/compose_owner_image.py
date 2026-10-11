#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compose owner calibration into a NEW private raw image; dry-run default.

Linux/debugfs only. No compilation, mounts, device I/O, upload or reboot.
Never prints calibration contents, MAC, individual calibration hash or paths.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PROFILES = {
    'acer-a1-840fhd': (1887436800, '/vendor/firmware/bcmdhd_aob.cal_43241_b4'),
    'dangol': (2147483648, '/vendor/firmware/nvram_ap6212.txt'),
}


def validate_calibration(data, device):
    if not 0 < len(data) <= 65536 or b'\0' in data:
        raise ValueError('unsupported calibration')
    text = data.decode('ascii')
    if re.search(r'(?i)PRIVATE KEY|adbkey|adb_keys', text) or re.search(
            r'(?im)^\s*(?:ssid|psk|password|passwd|passphrase)\s*=|\bnetwork\s*=\s*\{', text):
        raise ValueError('authentication material is not calibration')
    fields = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        key, separator, value = line.partition('=')
        if not separator or key in fields:
            raise ValueError('invalid calibration fields')
        fields[key] = value.strip()
    if device == 'acer-a1-840fhd':
        if any(fields.get(k) != v for k, v in
               {'boardtype': '0x5ef', 'boardrev': '0x1100', 'sromrev': '9'}.items()):
            raise ValueError('wrong board profile')
    elif device == 'dangol':
        if not {'boardtype', 'sromrev', 'macaddr'} <= fields.keys():
            raise ValueError('incomplete board profile')
    else:
        raise ValueError('unsupported device')
    if 'macaddr' in fields and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', fields['macaddr']):
        raise ValueError('invalid MAC syntax')
    return data


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def fs_read(image, command):
    result = subprocess.run(['debugfs', '-R', command, str(image)],
                            capture_output=True, check=True, timeout=60)
    return result.stdout, result.stderr


def filesystem_check(image):
    result = subprocess.run(['e2fsck', '-f', '-n', str(image)],
                            capture_output=True, timeout=600)
    if result.returncode:
        raise ValueError('filesystem consistency check failed')


def require_temp_path(folder):
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', folder):
        raise ValueError('unsupported temporary directory path')


def compose(source, owner_calibration, output, expected, device,
            apply=False, confirm_owner=False):
    if device not in PROFILES or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('supported device and explicit base checksum required')
    if apply and not confirm_owner:
        raise ValueError('explicit confirmation of own device calibration required')
    size, target = PROFILES[device]
    if source.is_symlink() or not source.is_file() or source.stat().st_size != size:
        raise ValueError('partition-sized regular raw input required')
    if owner_calibration.is_symlink() or not owner_calibration.is_file() or not 0 < owner_calibration.stat().st_size <= 65536:
        raise ValueError('regular owner calibration required')
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('new private output outside repository required')
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('existing real output parent required')
    data = validate_calibration(owner_calibration.read_bytes(), device)
    with source.open('rb') as stream:
        stream.seek(1080)
        if stream.read(2) != b'\x53\xef':
            raise ValueError('raw ext4 required, not sparse')
    if digest(source) != expected:
        raise ValueError('base checksum mismatch')
    filesystem_check(source)
    for directory in ('/vendor', '/vendor/firmware'):
        info, errors = fs_read(source, 'stat ' + directory)
        if not re.search(rb'\bType:\s+directory\b', info) or b'not found' in errors:
            raise ValueError('real firmware directories required')
    info, errors = fs_read(source, 'stat ' + target)
    if info.strip() or b'File not found' not in errors:
        raise ValueError('calibration destination must be absent')
    report = {'device': device, 'dry_run': not apply, 'owner_image_created': False,
              'calibration_readback_verified': False, 'calibration_hash_logged': False,
              'filesystem_integrity_verified': True, 'device_io': False,
              'image_is_private_owner_output': True, 'bootability_verified': False,
              'publication_approved': False}
    if not apply:
        return report
    if shutil.disk_usage(output.parent).free < size:
        raise ValueError('insufficient output free space')
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as destination, source.open('rb') as original:
        shutil.copyfileobj(original, destination, 1024 * 1024)
    if output.stat().st_size != size or digest(output) != expected:
        raise ValueError('base changed or short copy; preserve partial output')
    with tempfile.TemporaryDirectory(prefix='private-owner-calibration-') as folder:
        require_temp_path(folder)
        calibration = Path(folder) / 'owner.bin'
        label = Path(folder) / 'label.bin'
        calibration.write_bytes(data)
        calibration.chmod(0o600)
        label.write_bytes(b'u:object_r:vendor_file:s0\0')
        commands = ['write ' + str(calibration) + ' ' + target,
                    'set_inode_field ' + target + ' uid 0',
                    'set_inode_field ' + target + ' gid 0',
                    'set_inode_field ' + target + ' mode 0100644',
                    'ea_set -f ' + str(label) + ' ' + target + ' security.selinux']
        for command in commands:
            subprocess.run(['debugfs', '-w', '-R', command, str(output)],
                           capture_output=True, check=True, timeout=60)
    restored, _ = fs_read(output, 'cat ' + target)
    info, _ = fs_read(output, 'stat ' + target)
    label, _ = fs_read(output, 'ea_get ' + target + ' security.selinux')
    if restored != data or not re.search(rb'\bMode:\s+0644\b', info) or not re.search(rb'\bUser:\s+0\s+Group:\s+0\b', info):
        raise ValueError('owner calibration contents/permissions readback failed')
    if b'"u:object_r:vendor_file:s0\\000"' not in label:
        raise ValueError('owner calibration label readback failed')
    filesystem_check(output)
    if digest(source) != expected:
        raise ValueError('base changed; preserve output and investigate')
    report.update({'dry_run': False, 'owner_image_created': True,
                   'calibration_readback_verified': True,
                   'base_unchanged': True, 'private_owner_image_sha256': digest(output)})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, choices=sorted(PROFILES))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--calibration', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--base-sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-owner-input', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not sys.platform.startswith('linux'):
            raise ValueError('Linux/WSL required')
        print(json.dumps(compose(args.input, args.calibration, args.output, args.base_sha256,
                                 args.device, args.apply, args.confirm_owner_input), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({'error': 'owner composition refused or incomplete; preserve private partial output',
                          'host_output_may_exist': args.apply, 'device_io': False,
                          'calibration_hash_logged': False, 'publication_approved': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
