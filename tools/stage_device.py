#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage reviewed Dangol source into a new Android device tree; dry-run default."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'source/device/nexell/dangol/'


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('invalid path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '.git' in path.parts or str(path) != value:
        raise ValueError('unsafe path')
    return str(path)


def payload(root, name):
    path = root / PREFIX / relative(name)
    boundary = root / PREFIX
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(boundary.resolve()):
        raise ValueError('source outside reviewed tree')
    current = path.parent
    while current != boundary:
        if current.is_symlink():
            raise ValueError('symlink source parent')
        current = current.parent
    return path.read_bytes()


def stage(source, apply=False, root=ROOT):
    source = source.resolve(strict=True)
    if not (source / 'build/envsetup.sh').is_file():
        raise ValueError('not an Android workspace')
    output = source / 'device/nexell/dangol'
    if output.exists() or output.is_symlink():
        raise ValueError('destination already exists')
    for parent in (source / 'device', source / 'device/nexell'):
        if parent.is_symlink():
            raise ValueError('symlink destination parent')
    index = json.loads((root / 'source/dangol-device-provenance.json').read_text())
    if index['schema'] != 1 or index['device'] != 'dangol':
        raise ValueError('unexpected source index')
    planned = {}
    for entry in index['files']:
        name = relative(entry['path'])
        data = payload(root, name)
        if name in planned or len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('source fingerprint mismatch')
        planned[name] = data
    hwc = json.loads((root / 'source/dangol-hwc-provenance.json').read_text())
    if hwc['schema'] != 1:
        raise ValueError('unexpected HWC index')
    for entry in hwc['files']:
        if not entry['path'].startswith(PREFIX + 'experimental/'):
            raise ValueError('unexpected HWC source')
        name = relative(entry['path'][len(PREFIX):])
        data = payload(root, name)
        if name in planned or hashlib.sha256(data).hexdigest() != entry['published_sha256']:
            raise ValueError('HWC fingerprint mismatch')
        planned[name] = data
    if apply:
        output.mkdir(parents=True)
        for name, data in planned.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
    return {'device': 'dangol', 'files_preflighted': len(planned), 'dry_run': not apply,
            'device_sources_staged': apply, 'vendor_complete': False, 'rom_built': False,
            'device_io': False, 'image_publication_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(stage(args.source, args.apply), indent=2))
        return 0
    except (ValueError, OSError, KeyError):
        print(json.dumps({'error': 'staging refused; preserve any new partial destination', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
