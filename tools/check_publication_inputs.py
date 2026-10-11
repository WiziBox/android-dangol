#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tracked publication files only; never print suspected secret bytes."""
import json
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


def main():
    repository = Path(__file__).resolve().parents[1]
    try:
        raw = subprocess.check_output(['git', '-C', str(repository), 'ls-files', '-z'])
        names = [item.decode('utf-8') for item in raw.split(b'\0') if item]
        rejected = 0
        for name in names:
            path = repository.joinpath(*PurePosixPath(name).parts)
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('unsupported tracked file')
            if inspect_file(name, path.read_bytes()):
                rejected += 1
        print(json.dumps({'tracked_files_checked': len(names), 'rejected_files': rejected,
                          'contents_not_printed': True, 'history_and_release_assets_checked': False,
                          'whole_rom_or_license_clearance': False}))
        return 1 if rejected else 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        print(json.dumps({'error': 'publication input check failed; inspect locally'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
