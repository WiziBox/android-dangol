#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a new raw system image with deterministic zero sparse holes.

Preflight by default; --apply writes only a new host file, never a device.
Not a contents/license audit, flashing procedure or publication approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import zlib
from inspect_system import inspect, PARTITIONS


def expand(source, output, expected_sha256, device, apply=False):
    if source.is_symlink() or not source.is_file():
        raise ValueError('regular source required')
    if output.exists() or output.is_symlink() or output.resolve() == source.resolve() or output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('new output required')
    size = PARTITIONS[device]
    if not 0 < source.stat().st_size <= size + 32 * 1024 * 1024:
        raise ValueError('excessive source size')
    hashed = hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hashed.update(block)
        if hashed.hexdigest() != expected_sha256:
            raise ValueError('source SHA-256 mismatch')
        stream.seek(0)
        before = inspect(stream, size)
        report = {'device': device, 'source_format': before['format'],
                  'output_bytes': size, 'sparse_holes_zeroed_bytes': before['dont_care_bytes'],
                  'raw_sha256': before['expanded_zero_holes_sha256'],
                  'applied': False, 'device_io': False, 'publication_approved': False}
        if not apply:
            return report
        if not output.parent.is_dir() or output.parent.is_symlink() or shutil.disk_usage(output.parent).free < size:
            raise ValueError('output parent or free space missing')
        stream.seek(0)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as destination:
            after = inspect(stream, size, expanded_output=destination)
        if before != after or output.stat().st_size != size:
            raise ValueError('source changed; preserve but do not flash partial output')
    actual = hashlib.sha256()
    with output.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            actual.update(block)
    if actual.hexdigest() != report['raw_sha256']:
        raise ValueError('output readback checksum mismatch')
    report['applied'] = True
    report['host_output_checksum_verified'] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, choices=sorted(PARTITIONS))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(expand(args.input, args.output, args.sha256, args.device, args.apply), indent=2))
        return 0
    except (OSError, ValueError, KeyError, struct.error, zlib.error):
        print(json.dumps({'error': 'expansion refused or incomplete; keep partial output, do not flash', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
