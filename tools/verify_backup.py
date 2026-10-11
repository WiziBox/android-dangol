#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only integrity check of private Dangol partition backups (no device I/O)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

PARTITIONS = {
    'dangol-boot.img': 62914560,
    'dangol-p2.img': 3145728,
    'dangol-system.img': 2147483648,
    'dangol-p5.img': 67108864,
    'dangol-recovery.img': 67108864,
    'dangol-misc.img': 1048576,
}


def inventory(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('invalid backup directory')
    result = {}
    for name, size in PARTITIONS.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise ValueError('missing or unexpected partition backup')
        digest = hashlib.sha256()
        count = 0
        with path.open('rb') as stream:
            before = path.stat()
            for block in iter(lambda: stream.read(1048576), b''):
                count += len(block)
                digest.update(block)
            after = path.stat()
        if count != size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('backup changed during reading')
        result[name] = {'bytes': size, 'sha256': digest.hexdigest()}
    return result


def verify(directory, receipt):
    if not isinstance(receipt, dict) or set(receipt) != {'schema', 'device', 'files'}:
        raise ValueError('invalid receipt')
    if receipt['schema'] != 1 or receipt['device'] != 'dangol':
        raise ValueError('unsupported receipt')
    rows = receipt['files']
    if not isinstance(rows, dict) or set(rows) != set(PARTITIONS):
        raise ValueError('incomplete receipt')
    for name, row in rows.items():
        if (not isinstance(row, dict) or set(row) != {'bytes', 'sha256'}
                or type(row['bytes']) is not int or row['bytes'] != PARTITIONS[name]
                or not isinstance(row['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('invalid partition record')
    if inventory(directory) != rows:
        raise ValueError('backup differs from receipt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create-private-receipt', type=Path)
    group.add_argument('--verify-private-receipt', type=Path)
    args = parser.parse_args()
    try:
        if args.create_private_receipt:
            output = args.create_private_receipt
            if output.exists() or output.is_symlink() or not output.parent.is_dir():
                raise ValueError('output must be new')
            receipt = {'schema': 1, 'device': 'dangol', 'files': inventory(args.backup_dir)}
            with output.open('x', encoding='utf-8') as stream:
                output.chmod(0o600)
                json.dump(receipt, stream, indent=2)
        else:
            path = args.verify_private_receipt
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
                raise ValueError('invalid receipt file')
            verify(args.backup_dir, json.loads(path.read_text(encoding='utf-8')))
        print(json.dumps({'partition_files_checked': len(PARTITIONS), 'device_io': False,
                          'backup_contents_not_printed': True, 'restore_proven': False,
                          'redistribution_approved': False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'error': 'backup integrity check refused', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
