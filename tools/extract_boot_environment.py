#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract a private environment from the measured owner preboot backup, offline only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from check_boot_environment import inspect
from pack_boot import components, align, PAGE

PREBOOT_BYTES = 4915200
ENV_OFFSET = 3015168
ENV_BYTES = 16384


def extract(preboot, expected, boot):
    if not re.fullmatch('[0-9a-f]{64}', expected) or len(preboot) != PREBOOT_BYTES:
        raise ValueError('unsupported preboot backup')
    if hashlib.sha256(preboot).hexdigest() != expected:
        raise ValueError('preboot backup checksum mismatch')
    components(boot)
    sizes = struct.unpack_from('<9I', boot, 8)
    kernel, ramdisk, dtb = sizes[0], sizes[2], sizes[4]
    boot_bytes = PAGE + align(kernel, PAGE) + align(ramdisk, PAGE) + align(dtb, PAGE)
    environment = preboot[ENV_OFFSET:ENV_OFFSET + ENV_BYTES]
    report = inspect(environment, boot_bytes)
    report['preboot_checksum_verified'] = True
    report['owner_boot_components_validated'] = True
    report['environment_offset_autodetected'] = False
    report['publication_approved'] = False
    return environment, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preboot', type=Path, required=True)
    parser.add_argument('--preboot-sha256', required=True)
    parser.add_argument('--owner-boot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='write a new private host environment file')
    args = parser.parse_args()
    try:
        for path in (args.preboot, args.owner_boot):
            if path.is_symlink() or not path.is_file():
                raise ValueError('regular private input required')
        if args.preboot.stat().st_size != PREBOOT_BYTES or not 1632 <= args.owner_boot.stat().st_size <= 62914560:
            raise ValueError('unsupported input size')
        repository = Path(__file__).resolve().parents[1]
        if (args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir()
                or repository == args.output.resolve() or repository in args.output.resolve().parents):
            raise ValueError('new private output outside publication repository required')
        source = args.preboot.read_bytes()
        environment, report = extract(source, args.preboot_sha256, args.owner_boot.read_bytes())
        if args.apply:
            with args.output.open('xb') as stream:
                args.output.chmod(0o600)
                stream.write(environment)
            if args.output.read_bytes() != environment or args.preboot.read_bytes() != source:
                raise ValueError('readback or original preservation check failed')
        report['dry_run'] = not args.apply
        report['new_private_file_written'] = args.apply
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, TypeError, struct.error):
        print(json.dumps({'error': 'private environment extraction refused; preserve partial output', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
