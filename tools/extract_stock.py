#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract only reviewed inputs from an owner RAW ext4 system backup on Linux.

debugfs is read-only (no -w). No mounting, device access or image modification.
Android sparse images must first be converted with the pinned tree's simg2img.
"""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys

from import_vendor import CALIBRATION, calibration_valid, relative


def read_ext4(image, name, depth=0):
    relative(name)
    if depth > 8:
        raise ValueError('symlink depth exceeded')
    info = subprocess.run(['debugfs', '-R', 'stat /' + name, str(image)],
                          check=True, capture_output=True)
    if b'Type: symlink' in info.stdout:
        match = re.search(rb'Fast link dest: "([A-Za-z0-9_./-]+)"', info.stdout)
        if not match:
            raise ValueError('unsupported symlink')
        link = match[1].decode('ascii')
        target = posixpath.normpath(link if link.startswith('/') else posixpath.join(posixpath.dirname(name), link))
        return read_ext4(image, target.lstrip('/'), depth + 1)
    size = re.search(rb'\bSize:\s*(\d+)', info.stdout)
    if b'Type: regular' not in info.stdout or not size or not 0 < int(size[1]) <= 32 * 1024 * 1024:
        raise ValueError('missing or oversized regular input')
    result = subprocess.run(['debugfs', '-R', 'cat /' + name, str(image)],
                            check=True, capture_output=True)
    if len(result.stdout) != int(size[1]):
        raise ValueError('short stock read')
    return result.stdout


def extract(manifest, image, output):
    if manifest.get('schema') != 1 or manifest.get('device') != 'dangol' or manifest.get('owner_calibration') != CALIBRATION:
        raise ValueError('unexpected index')
    if not image.is_file() or output.exists() or output.is_symlink():
        raise ValueError('missing image or existing output')
    with image.open('rb') as stream:
        stream.seek(1080)
        if stream.read(2) != b'\x53\xef':
            raise ValueError('input must be raw ext4, not Android sparse')
    plan, seen = [], set()
    for row in manifest['files']:
        name = str(relative(row['source']))
        if name in seen or name == CALIBRATION:
            raise ValueError('duplicate input')
        seen.add(name)
        data = read_ext4(image, name)
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('stock input differs from supported baseline')
        plan.append((name, data))
    cal = read_ext4(image, CALIBRATION)
    calibration_valid(cal)
    plan.append((CALIBRATION, cal))
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('output parent must already exist')
    if image.resolve().is_relative_to(output.resolve()):
        raise ValueError('output cannot contain input image')
    output.mkdir(mode=0o700)
    for name, data in plan:
        path = output.joinpath(*relative(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o600)
    return {'stock_inputs_extracted': len(plan) - 1, 'owner_calibration_kept_private': True,
            'device_io': False, 'image_modified': False, 'redistribution_approved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system-image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        index = json.loads((Path(__file__).parents[1] / 'vendor-inputs/stock.json').read_text())
        print(json.dumps(extract(index, args.system_image, args.output), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print(json.dumps({'error': 'stock extraction refused; preserve any partial new output', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
