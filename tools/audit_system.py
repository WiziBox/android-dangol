#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Limited full system-image privacy inventory; never approves redistribution.

Linux: read-only debugfs, optional owner-specified simg2img, isolated temporary
conversion only. No mounts, device access, extracted filesystem or networking.
"""
import argparse
import base64
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile
from inspect_system import PARTITIONS, inspect

MAX_FILE = 192 * 1024 * 1024
MAX_ZIP = 384 * 1024 * 1024
KEY_NAMES = {'adb_keys', 'adbkey', 'adbkey.pub', 'authorized_keys'}
GOOGLE_APKS = {'phonesky', 'gmscore', 'prebuiltgmscore', 'googleservicesframework', 'googleservicesframeworklogin'}
OWNER_CALIBRATION = {'vendor/firmware/bcmdhd_aob.cal_43241_b4', 'vendor/firmware/nvram_ap6212.txt'}


def safe_path(value):
    path = PurePosixPath(value)
    if not re.fullmatch(r'[A-Za-z0-9_.+@/-]+', value) or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('unsupported filesystem path')
    return path


def safe_member(value):
    # ZIP members are read by ZipInfo, never passed to debugfs or extracted.
    # Android aapt-generated resource names legitimately contain '$'.
    path = PurePosixPath(value)
    if not value or any(ord(c) < 32 for c in value) or '\\' in value or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('unsafe archive member path')
    return path


def findings(name, data):
    reasons = []
    base = PurePosixPath(name).name.lower()
    if base in KEY_NAMES or base.endswith(('.pk8', '.p12', '.jks', '.keystore', '.priv')):
        reasons.append('authentication/signing key filename')
    pem = rb'-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----\s*([A-Za-z0-9+/=\r\n]+)\s*-----END \1-----'
    if re.search(pem, data):
        reasons.append('PEM private-key block')
    for token in re.findall(rb'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{699}=(?![A-Za-z0-9+/=])', data):
        decoded = base64.b64decode(token, validate=True)
        if len(decoded) == 524 and struct.unpack_from('<I', decoded)[0] == 64:
            reasons.append('serialized Android ADB approval key')
            break
    if name.endswith(('.txt', '.conf', '.cal', '.prop', '.rc')) or '.cal_' in base:
        if re.search(rb'(?im)^\s*(?:macaddr|mac_address|psk|password|ssid)\s*=|network\s*=\s*\{', data):
            reasons.append('owner calibration/network identity or credential field')
        if re.search(rb'(?m)^\s*(?:ro\.adb\.secure|ro\.secure)\s*=\s*0\s*$|\bsetprop\s+ro\.adb\.secure\s+0\b', data):
            reasons.append('insecure default ADB policy')
        if re.search(rb'(?m)^\s*(?:persist|service)\.adb\.tcp\.port\s*=\s*[1-9][0-9]*\s*$|\bsetprop\s+(?:persist|service)\.adb\.tcp\.port\s+[1-9][0-9]*\b', data):
            reasons.append('positive network ADB default/directive; trigger context needs review')
    if base.endswith('.apk') and PurePosixPath(base).stem in GOOGLE_APKS:
        reasons.append('unapproved Google application candidate')
    return [{'entry': name, 'reason': reason} for reason in reasons]


def scan_file(name, data):
    result = findings(name, data)
    if name.endswith(('.apk', '.jar', '.zip')):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 100000 or sum(x.file_size for x in entries) > MAX_ZIP:
                raise ValueError('archive inspection size exceeded')
            seen = set()
            for entry in entries:
                if entry.filename in seen:
                    raise ValueError('duplicate archive member')
                seen.add(entry.filename)
                if entry.is_dir():
                    continue
                safe_member(entry.filename)
                if entry.file_size > MAX_FILE:
                    raise ValueError('archive member too large')
                # zipfile verifies CRC while reading; never extract member paths.
                result.extend(findings(name + '!' + entry.filename, archive.read(entry)))
    return result


def directory_entries(data):
    rows = []
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('directory listing too large')
    for line in data.decode('utf-8', 'strict').splitlines():
        if not line:
            continue
        fields = line.split('/')
        if len(fields) != 8 or fields[0] or fields[-1]:
            raise ValueError('unsupported debugfs listing')
        inode, mode, uid, gid, name, size = fields[1:7]
        # e2fsprogs -p emits a trailing empty field after the size.
        if fields[7] or not inode.isdigit() or not re.fullmatch('[0-7]{6}', mode):
            raise ValueError('invalid directory entry')
        if name in ('.', '..') or inode == '0':
            continue
        safe_path(name)
        rows.append((name, int(mode, 8), int(size) if size else None))
    return rows


def debugfs(image, request):
    result = subprocess.run(['debugfs', '-R', request, str(image)], capture_output=True, check=True, timeout=60)
    if b'File not found' in result.stderr or b'not found by ext2_lookup' in result.stderr or b'Filesystem not open' in result.stderr:
        raise ValueError('filesystem read failed')
    if request.startswith('ls ') and not result.stdout.strip():
        raise ValueError('missing directory inventory')
    return result.stdout


def check_filesystem(image):
    result = subprocess.run(['e2fsck', '-f', '-n', str(image)], capture_output=True, timeout=600)
    if result.returncode != 0:
        raise ValueError('read-only filesystem consistency check failed')
    return True


def scan_image(image):
    queue, visited, report_findings = [''], set(), []
    files, symlinks, scanned_bytes, notice, calibration = 0, 0, 0, False, []
    while queue:
        directory = queue.pop()
        if directory in visited or len(visited) > 20000:
            raise ValueError('duplicate directory or inventory limit')
        visited.add(directory)
        for base, mode, size in directory_entries(debugfs(image, 'ls -p /' + directory)):
            name = str(safe_path(directory + '/' + base if directory else base))
            if stat.S_ISDIR(mode):
                queue.append(name)
            elif stat.S_ISREG(mode):
                if size is None or not 0 <= size <= MAX_FILE or files >= 20000:
                    raise ValueError('file inspection size exceeded')
                data = debugfs(image, 'cat /' + name) if size else b''
                if len(data) != size:
                    raise ValueError('short filesystem file read')
                try:
                    report_findings.extend(scan_file(name, data))
                except (ValueError, zipfile.BadZipFile) as error:
                    safe_reasons = {'archive inspection size exceeded', 'archive member too large',
                                    'duplicate archive member', 'unsupported filesystem path', 'unsafe archive member path'}
                    reason = str(error) if str(error) in safe_reasons else 'archive parsing failed'
                    raise ValueError('file inspection refused: ' + name + '; ' + reason) from error
                files += 1
                scanned_bytes += size
                notice |= name == 'etc/NOTICE.html.gz'
                if name in OWNER_CALIBRATION:
                    calibration.append(name)
            elif stat.S_ISLNK(mode):
                symlinks += 1
                report_findings.extend(findings(name, b''))
            else:
                raise ValueError('unsupported special filesystem entry')
    if not files:
        raise ValueError('empty system inventory')
    return {'regular_files_scanned': files, 'directories_scanned': len(visited),
            'file_bytes_scanned': scanned_bytes, 'symlinks_not_followed': symlinks,
            'notice_html_gz_present': notice, 'findings': report_findings,
            'owner_calibration_files_present': sorted(calibration),
            'owner_calibration_publication_clearance_verified': False,
            'limited_privacy_inventory_passed': not report_findings,
            'filesystem_integrity_verified': False, 'licenses_reviewed': False,
            'nested_archives_recursively_scanned': False,
            'device_io': False, 'publication_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=sorted(PARTITIONS), required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--simg2img', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--check-filesystem', action='store_true', help='also run e2fsck -f -n; never repair')
    args = parser.parse_args(argv)
    stage = 'preflight'
    try:
        if not sys.platform.startswith('linux') or args.report.exists() or args.report.is_symlink():
            raise ValueError('Linux and new report required')
        repository = Path(__file__).resolve().parents[1]
        if repository == args.report.resolve() or repository in args.report.resolve().parents:
            raise ValueError('report must stay outside publication repository')
        if args.image.is_symlink() or not args.image.is_file():
            raise ValueError('regular image file required; device nodes are forbidden')
        if not args.work_dir.is_dir() or args.work_dir.is_symlink():
            raise ValueError('existing real private work directory required')
        stage = 'image format'
        with args.image.open('rb') as stream:
            checked = inspect(stream, PARTITIONS[args.device])
        with tempfile.TemporaryDirectory(prefix='system-privacy-', dir=args.work_dir) as folder:
            image = args.image
            if checked['format'] == 'android-sparse-v1.0':
                if not args.simg2img or not args.simg2img.is_file() or shutil.disk_usage(folder).free < PARTITIONS[args.device]:
                    raise ValueError('conversion tool or free space missing')
                image = Path(folder) / 'converted.raw.img'
                stage = 'private sparse conversion'
                subprocess.run([str(args.simg2img.resolve()), str(args.image.resolve()), str(image)], check=True, timeout=600)
                image.chmod(0o600)
                with image.open('rb') as stream:
                    raw_check = inspect(stream, PARTITIONS[args.device])
                if raw_check['expanded_zero_holes_sha256'] != checked['expanded_zero_holes_sha256']:
                    raise ValueError('converted data differs from inspected sparse image')
            filesystem_checked = False
            if args.check_filesystem:
                stage = 'read-only filesystem consistency check'
                filesystem_checked = check_filesystem(image)
            stage = 'filesystem inventory'
            report = scan_image(image)
            report['filesystem_integrity_verified'] = filesystem_checked
        stage = 'new report write'
        with args.report.open('x', encoding='utf-8') as stream:
            args.report.chmod(0o600)
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps(report, indent=2))
        return 0 if report['limited_privacy_inventory_passed'] else 1
    except (OSError, ValueError, KeyError, struct.error, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) and str(error).startswith('file inspection refused: ') else type(error).__name__
        print(json.dumps({'error': 'system inventory incomplete or refused', 'stage': stage,
                          'detail': detail, 'publication_approved': False, 'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
