#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only Android v0 / Acer OSIP ramdisk publication audit.

Never extracts archive paths, contacts a device, prints key contents or modifies
an image. This is a limited boot audit, NOT an entire-ROM license/security gate.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zlib

MAX_IMAGE = 64 * 1024 * 1024
MAX_RAMDISK = 64 * 1024 * 1024


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def ramdisk_from_boot(image, device):
    if len(image) > MAX_IMAGE:
        raise ValueError('boot image exceeds inspection size limit')
    if device == 'dangol':
        if len(image) < 1632 or image[:8] != b'ANDROID!':
            raise ValueError('expected Android boot v0 image')
        kernel_size, _, ramdisk_size, _, _, _, _, page, version = struct.unpack_from('<9I', image, 8)
        if version != 0 or page != 2048 or not kernel_size:
            raise ValueError('unsupported dangol header version/page size')
        start = page + align(kernel_size, page)
        kind = 'android-v0'
    elif device == 'acer-a1-840fhd':
        if len(image) < 0x3200 or image[:4] != b'$OS$':
            raise ValueError('expected Acer OSIP boot container')
        checksum = 0
        for byte in image[:56]:
            checksum ^= byte
        if checksum:
            raise ValueError('invalid OSIP header checksum')
        sectors = struct.unpack_from('<I', image, 0x30)[0]
        if len(image) != 512 + sectors * 512:
            raise ValueError('OSIP declared payload size mismatch')
        kernel_size, ramdisk_size = struct.unpack_from('<II', image, 512 + 0x400)
        if kernel_size == 0 or kernel_size % 4096:
            raise ValueError('invalid OSIP kernel allocation')
        if image[0x3200 + 0x202:0x3200 + 0x206] != b'HdrS':
            raise ValueError('missing Linux bzImage header')
        start = 0x3200 + kernel_size
        kind = 'acer-osip'
    else:
        raise ValueError('unsupported device')
    if not ramdisk_size or start + ramdisk_size > len(image):
        raise ValueError('ramdisk range outside image')
    compressed = image[start:start + ramdisk_size]
    if compressed[:2] != b'\x1f\x8b':
        raise ValueError('unsupported ramdisk compression; gzip required')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(MAX_RAMDISK + 1)
    if len(raw) > MAX_RAMDISK:
        raise ValueError('expanded ramdisk exceeds inspection limit')
    return kind, raw


def cpio_entries(raw):
    position = 0
    seen = set()
    while True:
        header = raw[position:position + 110]
        if len(header) != 110 or header[:6] not in (b'070701', b'070702'):
            raise ValueError('invalid/truncated newc header')
        try:
            fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        except ValueError as error:
            raise ValueError('invalid newc numeric field') from error
        size, name_size, checksum = fields[6], fields[11], fields[12]
        if not 1 <= name_size <= 4096:
            raise ValueError('invalid newc name size')
        name_bytes = raw[position + 110:position + 110 + name_size]
        if len(name_bytes) != name_size or not name_bytes.endswith(b'\0') or b'\0' in name_bytes[:-1]:
            raise ValueError('invalid newc name')
        name = name_bytes[:-1].decode('utf-8', 'strict')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe archive path')
        canonical = str(path)
        if canonical in seen:
            raise ValueError('duplicate archive path')
        seen.add(canonical)
        data_start = align(position + 110 + name_size, 4)
        data_end = data_start + size
        next_position = align(data_end, 4)
        if next_position > len(raw):
            raise ValueError('truncated newc member')
        data = raw[data_start:data_end]
        if header[:6] == b'070702' and sum(data) & 0xffffffff != checksum:
            raise ValueError('newc CRC mismatch')
        if canonical == 'TRAILER!!!':
            if size or any(raw[next_position:]):
                raise ValueError('unexpected data after newc trailer')
            return
        yield canonical, data
        position = next_position


def audit_bytes(image, device):
    kind, raw = ramdisk_from_boot(image, device)
    findings = []
    count = 0
    secure_adb = False
    for name, data in cpio_entries(raw):
        count += 1
        basename = PurePosixPath(name).name.lower()
        if basename in ('adb_keys', 'adbkey', 'adbkey.pub', 'authorized_keys') or basename.endswith(('.pk8', '.p12', '.jks', '.keystore', '.priv')):
            findings.append({'entry': name, 'reason': 'authentication/signing key file'})
        if re.search(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|-----BEGIN (?:RSA )?PUBLIC KEY-----', data):
            findings.append({'entry': name, 'reason': 'embedded key material'})
        # Detect Android adb's fixed 524-byte public-key serialization without
        # recording its bytes, hash, comment, or host identity.
        for token in re.findall(rb'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{699}=(?![A-Za-z0-9+/=])', data):
            import base64
            decoded = base64.b64decode(token, validate=True)
            if len(decoded) == 524 and struct.unpack_from('<I', decoded)[0] == 64:
                findings.append({'entry': name, 'reason': 'embedded Android adb public key'})
                break
        if name.endswith(('.prop', '.rc')):
            if re.search(rb'(?m)^\s*ro\.adb\.secure\s*=\s*1\s*$', data):
                secure_adb = True
            if re.search(rb'(?m)^\s*(?:ro\.adb\.secure|ro\.secure)\s*=\s*0\s*$|\bsetprop\s+ro\.adb\.secure\s+0\b', data):
                findings.append({'entry': name, 'reason': 'disabled adb authentication/default privilege drop'})
    if not secure_adb:
        findings.append({'entry': '(ramdisk properties)', 'reason': 'explicit ro.adb.secure=1 not found'})
    return {'device': device, 'format': kind, 'bytes': len(image),
            'sha256': hashlib.sha256(image).hexdigest(), 'ramdisk_entries': count,
            'findings': findings, 'boot_key_audit_passed': not findings,
            'whole_rom_audited': False, 'publication_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, choices=['dangol', 'acer-a1-840fhd'])
    parser.add_argument('image', type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.image.is_file() or args.image.stat().st_size > MAX_IMAGE:
            raise ValueError('missing image or excessive size')
        report = audit_bytes(args.image.read_bytes(), args.device)
        print(json.dumps(report, indent=2))
        return 0 if report['boot_key_audit_passed'] else 1
    except (ValueError, OSError, EOFError, struct.error, zlib.error) as error:
        print(json.dumps({'boot_key_audit_passed': False, 'error': str(error), 'publication_approved': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
