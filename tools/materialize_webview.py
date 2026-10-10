#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize the exact pinned ARM/x86 WebView LFS input, without fetching.
Default: read-only validation. --apply replaces only the known LFS pointer.
Owner/download inputs are not bundled or approved for redistribution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

INPUTS = {
    'x86': ('fff97d58fdeb0b54d6ea55d293ee63283d0c6eb0',
            '462967f71cc897a344c97826f28b12d1e5b104bbc3261bb01576284aaf0b38a8', 142423540),
    'arm': ('b2639126d02b401ae8a8a7f3ca302633713a12e6',
            'b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11', 90257078),
}


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def pointer(oid, size):
    return ('version https://git-lfs.github.com/spec/v1\n'
            'oid sha256:' + oid + '\nsize ' + str(size) + '\n').encode()


def validate_asset(asset, abi, oid, size):
    if not asset.is_file() or asset.is_symlink() or asset.stat().st_size != size or fingerprint(asset) != oid:
        raise ValueError('WebView object size/hash mismatch')
    with zipfile.ZipFile(asset) as archive:
        entry = 'lib/' + ('armeabi-v7a' if abi == 'arm' else abi) + '/libwebviewchromium.so'
        # Some ARM packages use armeabi rather than armeabi-v7a.
        if entry not in archive.namelist() and not (abi == 'arm' and 'lib/armeabi/libwebviewchromium.so' in archive.namelist()):
            raise ValueError('missing expected native WebView library')
        if archive.testzip() is not None:
            raise ValueError('APK CRC failure')


def materialize(source, abi, asset, apply=False):
    revision, oid, size = INPUTS[abi]
    source = source.resolve(strict=True)
    project = source / 'external/chromium-webview/prebuilt' / abi
    if project.is_symlink() or not project.is_dir() or source not in project.resolve().parents:
        raise ValueError('invalid WebView project directory')
    actual = subprocess.check_output(['git', '-C', str(project), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != revision:
        raise ValueError('unexpected WebView source revision')
    target = project / 'webview.apk'
    if target.is_symlink() or not target.is_file():
        raise ValueError('invalid existing WebView input')
    expected_pointer = pointer(oid, size)
    already = target.stat().st_size == size and fingerprint(target) == oid
    if not already and (target.stat().st_size != len(expected_pointer) or target.read_bytes() != expected_pointer):
        raise ValueError('refuse to replace unknown or modified WebView input')
    validate_asset(asset, abi, oid, size)
    changed = False
    if apply and not already:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=project, prefix='.webview-', suffix='.partial', delete=False) as stream:
                temporary = Path(stream.name)
                with asset.open('rb') as input_stream:
                    for block in iter(lambda: input_stream.read(4 * 1024 * 1024), b''):
                        stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            validate_asset(temporary, abi, oid, size)
            if target.is_symlink() or target.read_bytes() != expected_pointer:
                raise ValueError('target changed during preparation')
            os.replace(temporary, target)
            temporary = None
            changed = True
        finally:
            # Only the tool-created temporary file is removed; never the input.
            if temporary is not None:
                temporary.unlink()
    return {'abi': abi, 'revision': revision, 'sha256': oid, 'bytes': size,
            'dry_run': not apply, 'already_materialized': already, 'changed': changed,
            'device_io': False, 'rom_built': False, 'redistribution_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--abi', required=True, choices=sorted(INPUTS))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(materialize(args.source, args.abi, args.input, args.apply), indent=2))
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError):
        print(json.dumps({'error': 'WebView materialization refused or failed', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
