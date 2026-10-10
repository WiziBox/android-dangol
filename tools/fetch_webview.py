#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fetch one exact pinned WebView object from the official LineageOS LFS service.
Only creates a new download directory; does not modify source or a device.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
from materialize_webview import INPUTS, validate_asset


def https_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('non-HTTPS or credential-bearing download URL')
    return value


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl)
        # Do not forward action authorization to another host on redirect.
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header('Authorization')
            redirected.remove_header('Cookie')
        return redirected


def download(abi, output, opener=None):
    revision, oid, size = INPUTS[abi]
    if output.exists() or output.is_symlink():
        raise ValueError('download output must be a new directory')
    endpoint = ('https://review.lineageos.org/LineageOS/'
                'android_external_chromium-webview_prebuilt_' + abi + '.git/info/lfs/objects/batch')
    opener = opener or urllib.request.build_opener(HTTPSRedirect())
    payload = json.dumps({'operation': 'download', 'transfers': ['basic'],
                          'objects': [{'oid': oid, 'size': size}]}).encode()
    request = urllib.request.Request(endpoint, data=payload, headers={
        'Content-Type': 'application/vnd.git-lfs+json',
        'Accept': 'application/vnd.git-lfs+json'})
    with opener.open(request, timeout=45) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('excessive LFS response')
    reply = json.loads(data)
    objects = reply['objects']
    if len(objects) != 1:
        raise ValueError('unexpected LFS object count')
    obj = objects[0]
    if obj.get('error') or obj['oid'] != oid or obj['size'] != size:
        raise ValueError('LFS object does not match pinned input')
    action = obj['actions']['download']
    url = https_url(action['href'])
    headers = action.get('header', {})
    if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
        raise ValueError('invalid LFS action headers')
    output.mkdir(mode=0o700)
    partial = output / 'webview.apk.partial'
    count = 0
    with opener.open(urllib.request.Request(url, headers=headers), timeout=45) as response, partial.open('xb') as stream:
        https_url(response.geturl())
        for block in iter(lambda: response.read(1024 * 1024), b''):
            count += len(block)
            if count > size:
                raise ValueError('oversized object')
            stream.write(block)
    validate_asset(partial, abi, oid, size)
    # Exclusive publication in the new directory: never replace a raced file.
    os.link(partial, output / 'webview.apk')
    partial.unlink()
    receipt = {'abi': abi, 'revision': revision, 'sha256': oid, 'bytes': size,
               'provider': 'official LineageOS LFS', 'device_io': False,
               'source_modified': False, 'redistribution_approved': False}
    with (output / 'download-receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--abi', required=True, choices=sorted(INPUTS))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(download(args.abi, args.output), indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'error': 'download refused or failed; preserve and inspect any new partial output',
                          'device_io': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
