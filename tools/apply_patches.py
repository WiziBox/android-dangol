#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate/apply a reviewed patch set to an exact, clean upstream source tree.

Dry-run by default. No fetching, resetting, cleaning, building or device I/O.
All projects are preflighted before any patch is applied. An application error
stops immediately; it never resets or deletes the user's source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def contained(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '\\' in relative:
        raise ValueError('invalid relative path')
    candidate = (root / relative).resolve()
    candidate.relative_to(root.resolve())
    if '.git' in Path(relative).parts or '..' in Path(relative).parts:
        raise ValueError('unsafe relative path')
    return candidate


def git(directory, *arguments):
    result = subprocess.run(['git', '-C', str(directory), *arguments],
                            capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('Git preflight/application failed; no automatic reset performed')
    return result.stdout


def preflight(source, index, repository):
    payload = json.loads(index.read_text(encoding='utf-8'))
    if payload.get('schema') != 1 or not isinstance(payload.get('patches'), list) or not payload['patches']:
        raise ValueError('unsupported or empty patch index')
    plan = []
    seen = set()
    for item in payload['patches']:
        project = item['project']
        if project in seen:
            raise ValueError('duplicate project in patch index')
        seen.add(project)
        directory = contained(source, project)
        patch = contained(repository, item['patch'])
        if not directory.is_dir() or not patch.is_file():
            raise ValueError('missing source project or patch')
        if Path(git(directory, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != directory:
            raise ValueError('project is not the root of its own Git checkout')
        base = item['base_commit']
        expected = item['sha256']
        if not re.fullmatch('[a-f0-9]{40}', base) or not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('invalid commit/hash in patch index')
        if hashlib.sha256(patch.read_bytes()).hexdigest() != expected:
            raise ValueError('patch hash mismatch')
        if git(directory, 'rev-parse', 'HEAD').decode().strip() != base:
            raise ValueError(f'wrong upstream commit: {project}')
        if git(directory, 'status', '--porcelain=v1', '--untracked-files=all').strip():
            raise ValueError(f'project is not clean: {project}; preserve/review existing changes')
        git(directory, 'apply', '--check', str(patch))
        plan.append((project, directory, patch))
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--index', type=Path)
    parser.add_argument('--apply', action='store_true', help='Actually apply after all preflight checks')
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    index = args.index or repository / 'patch-set.json'
    applied = []
    try:
        if not args.source.is_dir():
            raise ValueError('source tree does not exist')
        plan = preflight(args.source.resolve(), index, repository)
        if args.apply:
            for project, directory, patch in plan:
                # Repeat clean check to reduce accidental overlap with another
                # writer. No tool can protect against an uncoordinated process.
                if git(directory, 'status', '--porcelain=v1', '--untracked-files=all').strip():
                    raise ValueError(f'project changed since preflight: {project}')
                git(directory, 'apply', str(patch))
                applied.append(project)
        print(json.dumps({'preflighted_projects': len(plan), 'applied_projects': applied,
                          'dry_run': not args.apply, 'rom_built': False}, indent=2))
        return 0
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'error': str(error), 'applied_projects': applied,
                          'automatic_reset': False, 'rom_built': False}, indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
