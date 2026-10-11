#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage reviewed owner stock inputs into a NEW vendor directory, dry-run first.

No device I/O or downloads. Calibration stays private and is not fingerprinted
in the receipt. This tool grants no rights to redistribute stock binaries.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

CALIBRATION = 'vendor/firmware/nvram_ap6212.txt'


def relative(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', value):
        raise ValueError('invalid relative path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or str(p) != value or '.git' in p.parts:
        raise ValueError('unsafe path')
    if any(x.lower() in {'data', 'factory', 'adb_keys', 'adbkey', '.ssh'} for x in p.parts):
        raise ValueError('authentication or personal input')
    if p.suffix.lower() in {'.apk', '.pem', '.pk8', '.jks', '.keystore'}:
        raise ValueError('application or signing input')
    return p


def read(root, value):
    p = root.joinpath(*relative(value).parts)
    if not p.resolve().is_relative_to(root) or not p.is_file():
        raise ValueError('missing or escaping input')
    if not 0 < p.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError('input size out of bounds')
    return p.read_bytes()


def calibration_valid(data):
    if len(data) > 65536 or b'\x00' in data or b'PRIVATE KEY' in data:
        raise ValueError('unsafe calibration')
    text = data.decode('ascii')
    if re.search(r'(?im)^\s*(psk|password|ssid)\s*=', text) or re.search(r'network\s*=\s*\{', text):
        raise ValueError('network credentials are forbidden')
    fields = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        key, sep, value = line.partition('=')
        if not sep or key in fields:
            raise ValueError('invalid or duplicate calibration field')
        fields[key] = value
    if not {'boardtype', 'sromrev', 'macaddr'} <= fields.keys():
        raise ValueError('missing board calibration fields')
    if not re.fullmatch(r'[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}', fields['macaddr']):
        raise ValueError('invalid owner MAC address')


def stage(manifest, root, output, apply=False):
    if manifest.get('schema') != 1 or manifest.get('device') != 'dangol' or manifest.get('redistribution_approved') is not False:
        raise ValueError('wrong manifest')
    if manifest.get('owner_calibration') != CALIBRATION:
        raise ValueError('unexpected calibration path')
    root = root.resolve()
    if not root.is_dir() or output.exists() or output.is_symlink():
        raise ValueError('existing output or missing input root')
    target = output.resolve()
    if target.is_relative_to(root) or root.is_relative_to(target):
        raise ValueError('overlapping input/output')
    plan, names = [], set()
    for row in manifest['files']:
        source = str(relative(row['source']))
        if source == CALIBRATION or source.lower() in names or row['install'] != 'system/' + source:
            raise ValueError('duplicate or unexpected destination')
        names.add(source.lower())
        data = read(root, source)
        if type(row['bytes']) is not int or len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('input fingerprint mismatch')
        plan.append((source, data))
    if not plan:
        raise ValueError('empty manifest')
    cal = read(root, CALIBRATION)
    calibration_valid(cal)
    plan.append((CALIBRATION, cal))
    report = {'device': 'dangol', 'verified_stock_inputs': len(plan) - 1,
              'owner_calibration_validated': True, 'applied': False,
              'redistribution_approved': False, 'device_io': False,
              'kernel_requirement': 'unchanged owner stock kernel paired with stock bcmdhd.ko'}
    if not apply:
        return report
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('output parent must exist')
    output.mkdir(mode=0o700)
    for source, data in plan:
        path = output / 'proprietary/system' / source
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o600)
    makefile = '# SPDX-License-Identifier: Apache-2.0\n# Private owner inputs; do not redistribute.\nPRODUCT_COPY_FILES += \\\n'
    makefile += ' \\\n'.join('    vendor/nexell/dangol/proprietary/system/' + name + ':system/' + name for name, _ in plan) + '\n'
    (output / 'dangol-vendor.mk').write_text(makefile, encoding='utf-8')
    report['applied'] = True
    with (output / 'import-receipt.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        manifest = json.loads((Path(__file__).parents[1] / 'vendor-inputs/stock.json').read_text())
        print(json.dumps(stage(manifest, args.input_root, args.output, args.apply), indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'error': 'owner input import refused; preserve any partial new output', 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
