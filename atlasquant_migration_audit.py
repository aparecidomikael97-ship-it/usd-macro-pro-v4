"""Offline runtime inventory. Reads Git objects; never migrates or calls providers.

CLI: python atlasquant_migration_audit.py --source REF --target REF
JSON goes to stdout. Exit 2 means unresolved review items; 1 means read failure.
Syntax validity is NOT application schema validity or proof of freshness.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out


def _bad_constant(value):
    raise ValueError('non-finite JSON number')


def inspect_payload(path: str, raw: bytes) -> dict:
    result = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
              'syntax_valid': False, 'schema_validated': False,
              'freshness_validated': False, 'records': None, 'issues': []}
    try:
        text = raw.decode('utf-8-sig')
        suffix = Path(path).suffix.lower()
        if suffix in ('.json', '.jsonl'):
            parse = lambda s: json.loads(s, object_pairs_hook=_object,
                                         parse_constant=_bad_constant)
            if suffix == '.jsonl':
                rows = [parse(line) for line in text.splitlines() if line.strip()]
                if not rows or not all(isinstance(r, dict) for r in rows):
                    raise ValueError('empty or non-object JSONL')
            else:
                value = parse(text)
                if not isinstance(value, (dict, list)):
                    raise ValueError('non-container JSON')
                rows = value if isinstance(value, list) else [value]
            seen = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for field in ('sample_id', 'record_id', 'id'):
                    if field not in row:
                        continue
                    key = (field, json.dumps(row[field], sort_keys=True))
                    canonical = json.dumps(row, sort_keys=True)
                    if key in seen:
                        issue = 'duplicate_id' if seen[key] == canonical else 'conflicting_id'
                        if issue not in result['issues']:
                            result['issues'].append(issue)
                    seen[key] = canonical
            result['records'] = len(rows)
        elif suffix == '.csv':
            rows = list(csv.reader(io.StringIO(text), strict=True))
            if not rows or not rows[0] or any(not c.strip() for c in rows[0]):
                raise ValueError('empty CSV header')
            if len(set(rows[0])) != len(rows[0]):
                raise ValueError('duplicate CSV header')
            if any(len(r) != len(rows[0]) for r in rows[1:]):
                raise ValueError('inconsistent CSV row width')
            result['records'] = len(rows) - 1
            if len(set(map(tuple, rows[1:]))) != len(rows) - 1:
                result['issues'].append('duplicate_row')
        else:
            raise ValueError('unsupported format requires review')
        result['syntax_valid'] = True
    except (ValueError, UnicodeError, csv.Error, RecursionError):
        result['issues'].append('invalid_or_unsupported_payload')
    return result


def compare_payloads(source: dict[str, bytes], target: dict[str, bytes]) -> dict:
    files = []
    for path in sorted(source.keys() | target.keys()):
        a, b = source.get(path), target.get(path)
        state = ('target_only' if a is None else 'source_only' if b is None
                 else 'identical' if a == b else 'different')
        left = inspect_payload(path, a) if a is not None else None
        right = inspect_payload(path, b) if b is not None else None
        issues = sorted({i for v in (left, right) if v for i in v['issues']})
        budget = any(word in path.lower() for word in ('budget', 'quota', 'cache', 'series'))
        files.append({'path': path, 'state': state, 'source': left, 'target': right,
                      'budget_or_cache_review': budget,
                      'review_required': state != 'identical' or bool(issues) or budget,
                      'proposal': 'preserve_target' if state == 'target_only' else
                                  'no_copy_needed' if state == 'identical' else 'manual_review'})
    return {'files': files, 'review_items': sum(x['review_required'] for x in files),
            'inventory_empty': not files, 'automatic_migration_allowed': False,
            'promotion_allowed': False, 'application_schema_validated': False}


def _git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def resolve_ref(repo, ref):
    return _git(repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def inventory(repo, sha):
    if not re.fullmatch(r'[0-9a-f]{40,64}', sha):
        raise ValueError('immutable commit SHA required')
    entries = _git(repo, 'ls-tree', '-r', '-z', sha, '--', 'dados/').split(b'\0')
    result = {}
    for entry in entries:
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, blob = meta.split()
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('non-regular data entry requires review')
        path = name.decode('utf-8')
        result[path] = _git(repo, 'cat-file', 'blob', blob.decode('ascii'))
    return result


def audit_repository(repo, source_ref, target_ref):
    before = [resolve_ref(repo, source_ref), resolve_ref(repo, target_ref)]
    report = compare_payloads(inventory(repo, before[0]), inventory(repo, before[1]))
    after = [resolve_ref(repo, source_ref), resolve_ref(repo, target_ref)]
    report.update(source_sha=before[0], target_sha=before[1],
                  refs_stable=before == after, scope='all tracked regular files under dados/',
                  remote_refs_checked=False)
    report['blocked'] = (before != after or report['inventory_empty'] or
                         report['review_items'] > 0)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', default='.')
    p.add_argument('--source', required=True)
    p.add_argument('--target', required=True)
    args = p.parse_args()
    try:
        report = audit_repository(args.repo, args.source, args.target)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print(json.dumps({'blocked': True, 'error': 'inventory_read_failed',
                          'automatic_migration_allowed': False}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report['blocked'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
