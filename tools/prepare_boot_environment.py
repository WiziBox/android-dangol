#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare a private owner environment copy with sufficient boot read length."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import zlib
from check_boot_environment import inspect


def prepare(data, boot_bytes):
    report = inspect(data, boot_bytes)
    if report['read_length_sufficient']:
        return data, False
    end = data.find(b'\0\0', 4)
    rows = data[4:end].split(b'\0')
    command = next(row for row in rows if row.startswith(b'bootcmd='))
    match = re.match(rb'bootcmd=mmc read 0x7107f800 0x2580 (0x[0-9a-fA-F]+);', command)
    old = match[1]
    digits = len(old) - 2
    replacement = ('0x' + format(report['required_read_sectors'], '0%dx' % digits)).encode('ascii')
    if len(replacement) != len(old):
        raise ValueError('read length requires unsupported environment resizing')
    changed_command = command[:match.start(1)] + replacement + command[match.end(1):]
    # Operate on parsed entries, never on an unrelated variable containing similar text.
    rows[rows.index(command)] = changed_command
    payload = b'\0'.join(rows) + data[end:]
    output = struct.pack('<I', zlib.crc32(payload)) + payload
    if len(output) != len(data) or not inspect(output, boot_bytes)['read_length_sufficient']:
        raise ValueError('candidate verification failed')
    return output, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('--boot-image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='write a new host file only')
    args = parser.parse_args()
    try:
        for path in (args.environment, args.boot_image):
            if path.is_symlink() or not path.is_file():
                raise ValueError('invalid input')
        if args.environment.stat().st_size != 16384:
            raise ValueError('unsupported environment size')
        if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
            raise ValueError('output must be new')
        repository = Path(__file__).resolve().parents[1]
        if repository == args.output.resolve() or repository in args.output.resolve().parents:
            raise ValueError('private output must be outside publication repository')
        with args.boot_image.open('rb') as stream:
            if stream.read(8) != b'ANDROID!':
                raise ValueError('unsupported boot format')
        source = args.environment.read_bytes()
        candidate, changed = prepare(source, args.boot_image.stat().st_size)
        if args.apply:
            with args.output.open('xb') as stream:
                args.output.chmod(0o600)
                stream.write(candidate)
            if args.output.read_bytes() != candidate or args.environment.read_bytes() != source:
                raise ValueError('host readback mismatch')
        print(json.dumps({'dry_run': not args.apply, 'new_private_file_written': args.apply,
                          'read_length_changed': changed, 'other_environment_values_preserved': True,
                          'device_io': False, 'bootability_verified': False}))
        return 0
    except (OSError, ValueError, TypeError, StopIteration):
        print(json.dumps({'error': 'private environment preparation refused; preserve partial output',
                          'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
