#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pack a new unsigned Dangol v0 boot from owner kernel/DTB and a new ramdisk.

Offline only. Does not retain the template ramdisk, header identity, command
line or legacy unused word. Never flashes or establishes redistribution rights.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
from audit_boot import align, audit_bytes

PARTITION_SIZE = 62914560
PAGE = 2048
GEOMETRY = (0x10008000, 0x11000000, 0x10f00000, 0x10000100)


def components(template):
    if not 1632 <= len(template) <= PARTITION_SIZE or template[:8] != b'ANDROID!':
        raise ValueError('unsupported owner boot input')
    ksize, kaddr, rsize, raddr, dsize, daddr, tags, page, version = struct.unpack_from('<9I', template, 8)
    if (kaddr, raddr, daddr, tags) != GEOMETRY or page != PAGE or version != 0:
        raise ValueError('owner header geometry mismatch')
    if not ksize or not rsize or dsize < 40:
        raise ValueError('missing owner components')
    rstart = PAGE + align(ksize, PAGE)
    dstart = rstart + align(rsize, PAGE)
    end = dstart + dsize
    if end > len(template) or any(template[PAGE + ksize:rstart]) or any(template[rstart + rsize:dstart]) or any(template[end:]):
        raise ValueError('truncated, signed or nonzero padded owner image')
    kernel = template[PAGE:PAGE + ksize]
    dtb = template[dstart:end]
    if len(kernel) < 64 or kernel[56:60] != b'ARM\x64':
        raise ValueError('expected owner ARM64 Image')
    magic, total, structure, strings, reserve, fdt_version, compatible, cpu, strings_size, structure_size = struct.unpack_from('>10I', dtb)
    if magic != 0xd00dfeed or total != len(dtb) or fdt_version != 17 or compatible > 17:
        raise ValueError('unsupported DTB header')
    if structure < 40 or strings < 40 or reserve < 40 or reserve >= total or structure + structure_size > total or strings + strings_size > total:
        raise ValueError('DTB bounds mismatch')
    return kernel, dtb


def pack(template, ramdisk):
    kernel, dtb = components(template)
    if not ramdisk or len(ramdisk) > 16 * 1024 * 1024:
        raise ValueError('ramdisk size unsupported')
    header = bytearray(PAGE)
    header[:8] = b'ANDROID!'
    struct.pack_into('<10I', header, 8, len(kernel), GEOMETRY[0], len(ramdisk), GEOMETRY[1], len(dtb), GEOMETRY[2], GEOMETRY[3], PAGE, 0, 0)
    header[64:64 + len(b'buildvariant=userdebug')] = b'buildvariant=userdebug'
    digest = hashlib.sha1()
    for data in (kernel, ramdisk, dtb):
        digest.update(data)
        digest.update(struct.pack('<I', len(data)))
    header[576:596] = digest.digest()
    image = bytes(header)
    for data in (kernel, ramdisk, dtb):
        image += data + bytes(align(len(data), PAGE) - len(data))
    if len(image) > PARTITION_SIZE:
        raise ValueError('new boot exceeds partition')
    report = audit_bytes(image, 'dangol')
    if not report['boot_key_audit_passed']:
        raise ValueError('new ramdisk failed limited credential audit')
    report.update({'kernel_sha256': hashlib.sha256(kernel).hexdigest(),
                   'dtb_sha256': hashlib.sha256(dtb).hexdigest(),
                   'original_ramdisk_reused': False, 'header_identity_reused': False,
                   'bootability_verified': False, 'device_io': False,
                   'stock_module_pairing_required': True,
                   'uboot_read_sectors': align(len(image), 512) // 512})
    return image, report


def read_input(path, maximum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('invalid input')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('input exceeds limit')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True, type=Path)
    parser.add_argument('--ramdisk', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError('output exists')
        image, report = pack(read_input(args.template, PARTITION_SIZE), read_input(args.ramdisk, 16 * 1024 * 1024))
        if args.apply:
            with args.output.open('xb') as stream:
                stream.write(image)
        report.update({'dry_run': not args.apply, 'image_written': args.apply})
        print(json.dumps(report, indent=2))
        return 0
    except (ValueError, OSError, EOFError, struct.error, zlib.error):
        print(json.dumps({'error': 'Dangol boot packaging refused; preserve any partial new output', 'publication_approved': False, 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
