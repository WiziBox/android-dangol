#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inspect a private 16 KiB Dangol environment backup; never modify or flash it."""
import argparse
from pathlib import Path
import re
import struct
import sys
import json
import zlib

PROFILE = re.compile(rb'mmc read 0x7107f800 0x2580 (0x[0-9a-fA-F]+);dtimg load_mmc 0x20d80 0x7A000000 0; bootm 0x7107f800 723ac000 0x7A000000')
PARTITION_BYTES = 62914560


def inspect(data, boot_bytes):
    if type(boot_bytes) is not int or not 1632 <= boot_bytes <= PARTITION_BYTES:
        raise ValueError('unsupported boot size')
    if len(data) != 16384 or struct.unpack_from('<I', data)[0] != zlib.crc32(data[4:]):
        raise ValueError('unsupported environment or bad CRC')
    payload = data[4:]
    end = payload.find(b'\0\0')
    if end < 0 or any(byte not in (0, 255) for byte in payload[end + 2:]):
        raise ValueError('unsupported environment termination')
    entries = {}
    for row in payload[:end].split(b'\0'):
        key, separator, value = row.partition(b'=')
        if not separator or not re.fullmatch(rb'[A-Za-z0-9_#.-]+', key) or key in entries:
            raise ValueError('unsupported environment entry')
        entries[key] = value
    match = PROFILE.fullmatch(entries.get(b'bootcmd', b''))
    if not match:
        raise ValueError('unsupported boot command profile')
    count = int(match[1], 16)
    if not 0 < count <= PARTITION_BYTES // 512:
        raise ValueError('read extends beyond supported boot partition size')
    required = (boot_bytes + 511) // 512
    return {'environment_crc_valid': True, 'boot_command_profile_supported': True,
            'configured_read_sectors': count, 'required_read_sectors': required,
            'read_length_sufficient': count >= required, 'device_io': False,
            'environment_modified': False, 'environment_contents_not_printed': True,
            'target_partition_and_ram_verified': False, 'bootability_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('--boot-image', type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in (args.environment, args.boot_image):
            if path.is_symlink() or not path.is_file():
                raise ValueError('invalid input')
        if args.environment.stat().st_size != 16384:
            raise ValueError('unsupported environment size')
        with args.boot_image.open('rb') as stream:
            if stream.read(8) != b'ANDROID!':
                raise ValueError('unsupported boot format')
        report = inspect(args.environment.read_bytes(), args.boot_image.stat().st_size)
        print(json.dumps(report, indent=2))
        return 0 if report['read_length_sufficient'] else 1
    except (OSError, ValueError, TypeError):
        print(json.dumps({'error': 'private environment inspection refused', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
