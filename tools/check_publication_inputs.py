#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tracked publication files only; never print suspected secret bytes."""
import json
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

FORBIDDEN_SUFFIXES = {'.img', '.bin', '.so', '.ko', '.apk', '.zip', '.pk8',
                      '.p12', '.pfx', '.jks', '.keystore'}
KEY_HEADER = re.compile(rb'(?m)^-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?$')


def inspect_file(name, data):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('invalid tracked path')
    base = path.name.lower()
    if (path.suffix.lower() in FORBIDDEN_SUFFIXES
            or base in {'adb_keys', 'authorized_keys'}
            or base.startswith('adbkey')
            or base in {'id_rsa', 'id_ed25519', 'id_ecdsa'}
            or any(part.lower() in {'backup', 'proprietary', 'downloads', 'out'} for part in path.parts)):
        return 'forbidden-private-or-binary-path'
    if KEY_HEADER.search(data):
        return 'private-key-header'
    if path.suffix.lower() == '.json':
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            return None
        if isinstance(value, dict) and value.get('device') == 'dangol' and value.get('schema') == 1:
            files = value.get('files')
            if isinstance(files, dict) and 'dangol-system.img' in files:
                return 'private-owner-backup-receipt'
    return None


def staged_inputs(repository):
    raw = subprocess.check_output(['git', '-C', str(repository), 'diff', '--cached',
                                   '--name-only', '-z', '--diff-filter=ACMR'])
    for item in raw.split(b'\0'):
        if not item:
            continue
        name = item.decode('utf-8')
        records = subprocess.check_output(['git', '-C', str(repository), 'ls-files',
                                          '--stage', '-z', '--', name]).split(b'\0')
        records = [row for row in records if row]
        if len(records) != 1:
            raise ValueError('unsupported index entry')
        metadata, stored_name = records[0].split(b'\t', 1)
        mode, object_id, stage = metadata.split(b' ')
        if mode not in (b'100644', b'100755') or stage != b'0' or stored_name != item:
            raise ValueError('unsupported staged file')
        size = int(subprocess.check_output(['git', '-C', str(repository), 'cat-file', '-s', object_id.decode('ascii')]))
        if size > 32 * 1024 * 1024:
            raise ValueError('oversized staged file')
        data = subprocess.check_output(['git', '-C', str(repository), 'cat-file', 'blob', object_id.decode('ascii')])
        if len(data) != size:
            raise ValueError('short staged object read')
        yield name, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='check actual added/modified index blobs before commit')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    try:
        raw = subprocess.check_output(['git', '-C', str(repository), 'ls-files', '-z'])
        names = [item.decode('utf-8') for item in raw.split(b'\0') if item]
        rejected = 0
        def working_inputs():
            for name in names:
                path = repository.joinpath(*PurePosixPath(name).parts)
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError('unsupported tracked file')
                yield name, path.read_bytes()
        checked = 0
        for name, data in staged_inputs(repository) if args.staged else working_inputs():
            checked += 1
            if inspect_file(name, data):
                rejected += 1
        print(json.dumps({'tracked_files_checked': checked, 'staged_blobs_checked': args.staged, 'rejected_files': rejected,
                          'contents_not_printed': True, 'history_and_release_assets_checked': False,
                          'whole_rom_or_license_clearance': False}))
        return 1 if rejected else 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        print(json.dumps({'error': 'publication input check failed; inspect locally'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
