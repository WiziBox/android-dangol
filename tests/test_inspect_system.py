# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
try:
    import inspect_system as tool
finally:
    sys.path.pop(0)


def filesystem():
    data = bytearray(4096)
    data[1080:1082] = b'\x53\xef'
    struct.pack_into('<I', data, 1028, 4)
    return bytes(data)


def sparse(crc=True):
    raw = filesystem()
    chunks = struct.pack('<2H2I', 0xCAC1, 0, 1, 12 + 4096) + raw
    chunks += struct.pack('<2H2I', 0xCAC2, 0, 1, 16) + b'ABCD'
    chunks += struct.pack('<2H2I', 0xCAC3, 0, 1, 12)
    expanded = raw + b'ABCD' * 1024 + bytes(4096)
    checksum = zlib.crc32(expanded)
    if crc:
        chunks += struct.pack('<2H2I', 0xCAC4, 0, 0, 16) + struct.pack('<I', checksum)
    header = struct.pack('<I4H4I', tool.MAGIC, 1, 0, 28, 12, 4096, 3, 4 if crc else 3, checksum)
    return header + chunks, expanded


class SystemTests(unittest.TestCase):
    def test_raw_exact_size(self):
        result = tool.inspect(io.BytesIO(filesystem()), 4096)
        self.assertEqual(result['format'], 'raw')
        self.assertFalse(result['contents_privacy_audited'])

    def test_sparse_raw_fill_hole_crc(self):
        image, expanded = sparse()
        result = tool.inspect(io.BytesIO(image), len(expanded))
        self.assertEqual(result['expanded_zero_holes_sha256'], hashlib.sha256(expanded).hexdigest())
        self.assertEqual(result['dont_care_bytes'], 4096)
        self.assertEqual(result['crc_chunks_checked'], 1)

    def test_header_crc_mismatch_refused(self):
        image, expanded = sparse()
        image = bytearray(image)
        image[24] ^= 1
        with self.assertRaises(ValueError):
            tool.inspect(io.BytesIO(image), len(expanded))

    def test_chunk_crc_mismatch_refused(self):
        image, expanded = sparse()
        image = image[:-1] + bytes([image[-1] ^ 1])
        with self.assertRaises(ValueError):
            tool.inspect(io.BytesIO(image), len(expanded))

    def test_short_or_extra_input_refused(self):
        image, expanded = sparse()
        for broken in (image[:-10], image + b'TRAILER'):
            with self.subTest(size=len(broken)), self.assertRaises(ValueError):
                tool.inspect(io.BytesIO(broken), len(expanded))

    def test_partition_and_superblock_bounds(self):
        with self.assertRaises(ValueError):
            tool.inspect(io.BytesIO(filesystem()), 2048)
        data = bytearray(filesystem())
        struct.pack_into('<I', data, 1028, 100000)
        with self.assertRaises(ValueError):
            tool.inspect(io.BytesIO(data), 4096)

    def test_unknown_chunk_refused(self):
        image, expanded = sparse()
        image = bytearray(image)
        struct.pack_into('<H', image, 28, 0xFFFF)
        with self.assertRaises(ValueError):
            tool.inspect(io.BytesIO(image), len(expanded))
