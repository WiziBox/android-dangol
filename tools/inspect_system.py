#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only sparse/raw system format and size inspection, not a content audit.

Format facts checked against the pinned Android libsparse/sparse_format.h.
Never expands to disk, contacts a device or approves licensing/publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

PARTITIONS = {'acer-a1-840fhd': 1887436800, 'dangol': 2147483648}
MAGIC = 0xED26FF3A
BUFFER = 1024 * 1024


def exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('truncated image')
    return data


def inspect(stream, partition_bytes, expanded_output=None):
    checksum, expanded_hash, prefix, expanded = 0, hashlib.sha256(), bytearray(), 0

    def consume(data):
        nonlocal checksum, expanded
        expanded += len(data)
        if expanded > partition_bytes:
            raise ValueError('expanded image exceeds partition')
        if len(prefix) < 2048:
            prefix.extend(data[:2048 - len(prefix)])
        checksum = zlib.crc32(data, checksum)
        expanded_hash.update(data)
        if expanded_output is not None:
            expanded_output.write(data)

    def consume_repeat(pattern, count):
        buffer = pattern * (BUFFER // len(pattern))
        while count:
            length = min(count, len(buffer))
            consume(buffer[:length])
            count -= length

    first = exact(stream, 4)
    chunks, holes, crc_chunks, image_crc = 0, 0, 0, 0
    if struct.unpack('<I', first)[0] == MAGIC:
        major, minor, fh, ch, block, blocks, chunks, image_crc = struct.unpack('<4H4I', exact(stream, 24))
        if (major, minor, fh, ch) != (1, 0, 28, 12) or not 4 <= block <= BUFFER or block % 4:
            raise ValueError('unsupported sparse header')
        if blocks * block != partition_bytes or not 1 <= chunks <= 1000000:
            raise ValueError('sparse image is not a complete supported partition image')
        output_blocks = 0
        for _ in range(chunks):
            kind, reserved, count, total = struct.unpack('<2H2I', exact(stream, 12))
            if reserved or count > blocks - output_blocks:
                raise ValueError('invalid chunk bounds')
            length = count * block
            if kind == 0xCAC1:
                if not count or total != 12 + length:
                    raise ValueError('invalid raw chunk')
                remaining = length
                while remaining:
                    data = exact(stream, min(remaining, BUFFER))
                    consume(data)
                    remaining -= len(data)
            elif kind == 0xCAC2:
                if not count or total != 16:
                    raise ValueError('invalid fill chunk')
                consume_repeat(exact(stream, 4), length)
            elif kind == 0xCAC3:
                if not count or total != 12:
                    raise ValueError('invalid dont-care chunk')
                holes += length
                consume_repeat(b'\0', length)
            elif kind == 0xCAC4:
                if count or total != 16 or struct.unpack('<I', exact(stream, 4))[0] != checksum:
                    raise ValueError('invalid CRC32 chunk')
                crc_chunks += 1
            else:
                raise ValueError('unknown sparse chunk type')
            output_blocks += count
        if output_blocks != blocks or (image_crc and image_crc != checksum):
            raise ValueError('sparse block/checksum mismatch')
        if stream.read(1):
            raise ValueError('unexpected sparse trailer')
        kind = 'android-sparse-v1.0'
    else:
        consume(first)
        while True:
            data = stream.read(BUFFER)
            if not data:
                break
            consume(data)
        kind = 'raw'
    if expanded != partition_bytes:
        raise ValueError('image does not cover the supported partition size')
    if len(prefix) < 2048 or prefix[1080:1082] != b'\x53\xef':
        raise ValueError('not an ext4 system filesystem')
    superblock = prefix[1024:2048]
    log_block = struct.unpack_from('<I', superblock, 24)[0]
    if log_block > 6:
        raise ValueError('invalid ext4 block size')
    fs_blocks = struct.unpack_from('<I', superblock, 4)[0]
    incompat = struct.unpack_from('<I', superblock, 96)[0]
    if incompat & 0x80:
        fs_blocks |= struct.unpack_from('<I', superblock, 0x150)[0] << 32
    filesystem_bytes = fs_blocks * (1024 << log_block)
    if not 0 < filesystem_bytes <= expanded:
        raise ValueError('ext4 superblock exceeds image')
    return {'format': kind, 'expanded_bytes': expanded, 'filesystem_bytes': filesystem_bytes,
            'expanded_zero_holes_sha256': expanded_hash.hexdigest(), 'expanded_crc32': '%08x' % checksum,
            'sparse_chunks': chunks, 'crc_chunks_checked': crc_chunks,
            'embedded_image_checksum_present': bool(image_crc),
            'embedded_image_checksum_verified': True if image_crc else None,
            'dont_care_bytes': holes, 'dont_care_interpretation': 'zero bytes for hash/CRC only; actual flash may retain old blocks',
            'format_and_size_passed': True, 'filesystem_integrity_verified': False,
            'contents_privacy_audited': False, 'device_io': False, 'publication_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=sorted(PARTITIONS), required=True)
    parser.add_argument('image', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.image.is_symlink() or not args.image.is_file() or args.image.stat().st_size > PARTITIONS[args.device] + 16 * 1024 * 1024:
            raise ValueError('missing or excessive image')
        with args.image.open('rb') as stream:
            print(json.dumps(inspect(stream, PARTITIONS[args.device]), indent=2))
        return 0
    except (OSError, ValueError, struct.error):
        print(json.dumps({'error': 'system format/size inspection refused', 'device_io': False, 'publication_approved': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
