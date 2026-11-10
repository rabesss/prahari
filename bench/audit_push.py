#!/usr/bin/env python3
"""Inspect every added or modified blob in a complete, ancestral Git range.

--hidden-check is a controller-only supplementary scan, not a disclosure proof.
"""
import argparse
from collections import deque
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

CODE = re.compile(r'(?:.*/)?[^/]+\.(?:py|sh|md|txt|toml|cfg|html|css|js)$|(?:.*/)?\.gitignore$|^bin/[^/]+$|^candidates/[^/]+/bin/[^/]+$|^\.github/workflows/[^/]+\.yml$')
CONFIG = re.compile(r'^(?:candidates/[^/]+/config\.json|models/registry\.json|eval/weights\.json|bench/[^/]+\.json)$')
ARTIFACT = re.compile(r'^candidates/[^/]+/artifacts/[^/]+\.joblib$')
RECORD = re.compile(r'^research/evals/[^/]+/(summary|details)\.json$')
LOG = re.compile(r'^research/evals/[^/]+/(run|app|tests|guard)\.log$')
RESULT = re.compile(r'^bench/results/[^/]+\.json$')
SYNTH = re.compile(r'^(?:research/stress|bench/fixtures)/[^/]+\.jsonl$')
ITEM_ID = re.compile(r'(?:\b(?:sms|url|flow|ind|indic|ex|exp)[-_][0-9a-f]{6,}\b|\bflow-te-\d+\b)', re.I)
# Construct patterns without embedding token-shaped examples in this source.
SECRET = re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bhf_[A-Za-z0-9]{20,}\b|\bsk-[A-Za-z0-9_-]{20,}\b|-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\bpassword\s*[:=]\s*["\']?[^\s"\']{4,}', re.I)
STATUS = [re.compile(p) for p in (
    r'^== (?:predict --task (?:sms|url|flow)|explain --in) rc=-?\d+ timeout=(?:True|False) wall_s=\d+(?:\.\d+)? peak_rss_mb=\d+(?:\.\d+)?\s*$',
    r'^=+ (?:\d+ (?:passed|failed|skipped|error|errors|warnings?)(?:, | in |$))[^\r\n]*=+\s*$',
    r'^[.s]+\s+\[100%\]\s*$',
    r'^\d+ passed(?:, \d+ (?:skipped|warnings?))? in \d+(?:\.\d+)?s\s*$',
    r'^(?:SELFTEST|selftest)\s*(?::|=)?\s*OK\s*$',
)]


SELFTEST_KEYS = {'verdict', 'score', 'evidence'}


def selftest_line(line):
    """bin/app --selftest prints one JSON list of results for the presets hard-coded in candidates/*/app/server.py."""
    try:
        value = json.loads(line)
    except ValueError:
        return False
    if not isinstance(value, list) or not 1 <= len(value) <= 5:
        return False
    for r in value:
        if not isinstance(r, dict) or not set(r) <= SELFTEST_KEYS or r.get('verdict') not in ('malicious', 'benign', 'uncertain'):
            return False
        if type(r.get('score')) not in (int, float):
            return False
        ev = r.get('evidence', [])
        if not isinstance(ev, list) or len(ev) > 10 or any(not isinstance(e, str) or len(e) > 200 or ITEM_ID.search(e) for e in ev):
            return False
    return True


def git(*args, binary=False):
    result = subprocess.run(['git', '--no-replace-objects', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout if binary else result.stdout.decode('utf-8', 'strict').strip()


def json_ok(value):
    if value is None or type(value) in (int, float, bool):
        return True
    if isinstance(value, str):
        return len(value) <= 200 and not ITEM_ID.search(value)
    if isinstance(value, list):
        return len(value) <= 50 and all(json_ok(x) for x in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and len(k) <= 200 and not ITEM_ID.search(k) and json_ok(v) for k, v in value.items())
    return False


def valid_json(data, lines=False):
    try:
        def reject(x):
            raise ValueError(x)
        values = [json.loads(x, parse_constant=reject) for x in data.decode('utf-8').splitlines() if x.strip()] if lines else [json.loads(data, parse_constant=reject)]
        return bool(values) and all(json_ok(x) for x in values)
    except (ValueError, UnicodeError, RecursionError):
        return False


def norm(s):
    s = re.sub(r'\d', '0', s.lower())
    return re.sub(r'[^a-z0\u0900-\u097f]+', ' ', s).strip()


class Matcher:
    """Aho-Corasick matcher, linear in input plus matches."""
    def __init__(self, patterns):
        self.nodes = [{}]; self.fail = [0]; self.end = [False]
        for pattern in patterns:
            n = 0
            for c in pattern:
                if c not in self.nodes[n]:
                    self.nodes[n][c] = len(self.nodes)
                    self.nodes.append({}); self.fail.append(0); self.end.append(False)
                n = self.nodes[n][c]
            self.end[n] = True
        q = deque(self.nodes[0].values())
        while q:
            n = q.popleft()
            for c, child in self.nodes[n].items():
                q.append(child); f = self.fail[n]
                while f and c not in self.nodes[f]: f = self.fail[f]
                self.fail[child] = self.nodes[f].get(c, 0)
                self.end[child] |= self.end[self.fail[child]]

    def contains(self, text):
        n = 0
        for c in text:
            while n and c not in self.nodes[n]: n = self.fail[n]
            n = self.nodes[n].get(c, 0)
            if self.end[n]: return True
        return False


def hidden_matchers():
    # Only invoked by the controller. Missing or malformed input fails closed.
    root = Path('/var/tmp/arm-bharat-ai-soc-data/hidden')
    paths = [root / name for name in ('sms_test.jsonl', 'url_test.jsonl', 'indic_test.jsonl', 'flow_test.jsonl', 'explain_set.jsonl')]
    if any(not path.is_file() for path in paths):
        raise ValueError('hidden check input unavailable')
    ids, texts = set(), set()
    for path in paths:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError('hidden check input malformed')
            ids.add(row['id'].lower())
            for key in ('text', 'url', 'input'):
                if isinstance(row.get(key), str):
                    value = norm(row[key])
                    if len(value) >= 25: texts.add(value)
    if not ids or not texts: raise ValueError('hidden check input incomplete')
    return Matcher(ids | texts)


def main():
    p = argparse.ArgumentParser(); p.add_argument('base'); p.add_argument('sha'); p.add_argument('--hidden-check', action='store_true')
    args = p.parse_args()
    try:
        if git('rev-parse', '--is-shallow-repository') != 'false': raise ValueError('shallow history')
        base = git('rev-parse', '--verify', args.base + '^{commit}')
        head = git('rev-parse', '--verify', args.sha + '^{commit}')
        subprocess.run(['git', '--no-replace-objects', 'merge-base', '--is-ancestor', base, head], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        commits = git('rev-list', '--topo-order', f'{base}..{head}').splitlines()
        if args.hidden_check:
            def timeout(_signum, _frame): raise TimeoutError('hidden check exceeded 10 minutes')
            signal.signal(signal.SIGALRM, timeout); signal.alarm(600)
            os.nice(10)
            matcher = hidden_matchers()
        else: print('hidden check SKIPPED (allowlist mode)')
        failures = set(); artifacts = set(); seen = set(); blob_cache = {}; hidden_hits = set()
        for commit in commits:
            # -m includes merge changes relative to every parent, --root covers root commits.
            raw = git('diff-tree', '--root', '-m', '--no-commit-id', '-r', '--no-renames', '--diff-filter=ACMT', '--raw', '-z', commit, binary=True)
            fields = raw.split(b'\0'); i = 0
            while i < len(fields) and fields[i]:
                meta = fields[i].decode('ascii').split(); path = fields[i+1].decode('utf-8', 'surrogateescape'); i += 2
                mode, oid = meta[1], meta[3]
                key = (path, oid, mode)
                if key in seen: continue
                seen.add(key)
                def fail(rule): failures.add((path, rule))
                if mode not in ('100644', '100755'):
                    fail('non-regular blob'); continue
                rules = [('code/docs', CODE.fullmatch(path)), ('config', CONFIG.fullmatch(path)), ('artifact', ARTIFACT.fullmatch(path)), ('eval JSON', RECORD.fullmatch(path) or RESULT.fullmatch(path)), ('eval log', LOG.fullmatch(path)), ('ledger', path == 'research/evals/ledger.jsonl'), ('synthetic', SYNTH.fullmatch(path))]
                matched = [name for name, match in rules if match]
                if len(matched) != 1:
                    fail('path not uniquely allowlisted'); continue
                rule = matched[0]
                size = int(git('cat-file', '-s', oid))
                limit = {'code/docs': 1_000_000, 'config': 256_000, 'artifact': 5_000_000, 'eval log': 4_000, 'eval JSON': 1_000_000, 'ledger': 1_000_000, 'synthetic': 1_000_000}[rule]
                if size > limit: fail(f'{rule} size limit'); continue
                if rule == 'artifact': artifacts.add((path, oid, size)); continue
                if oid not in blob_cache: blob_cache[oid] = git('cat-file', 'blob', oid, binary=True)
                data = blob_cache[oid]
                if SECRET.search(data): fail('secret pattern')
                if rule in ('eval JSON', 'ledger') and not valid_json(data, rule == 'ledger'): fail('eval JSON leaf/array/id policy')
                if rule == 'eval log':
                    try: lines = data.decode('utf-8').splitlines()
                    except UnicodeError: lines = ['<invalid>']
                    is_app = path.endswith('/app.log')
                    if any(not (any(rx.fullmatch(line) for rx in STATUS) or (is_app and selftest_line(line))) for line in lines): fail('non-status log line')
                if args.hidden_check:
                    try: decoded = data.decode('utf-8')
                    except UnicodeError: fail('hidden check undecodable text'); continue
                    if matcher.contains(decoded.lower()) or matcher.contains(norm(decoded)): hidden_hits.add(path); fail('hidden-content match')
        for path, oid, size in sorted(artifacts): print(f'ARTIFACT {path} blob={oid} bytes={size}')
        for path, rule in sorted(failures): print(f'FAIL {path}: {rule}')
        if args.hidden_check: print(f'hidden check: {len(hidden_hits)} matched paths')
        print(f'audited {base}..{head}: {len(commits)} commits, {len(seen)} path/blob entries; {len(failures)} failure(s)')
        return 1 if failures else 0
    except (subprocess.CalledProcessError, ValueError, OSError, UnicodeError, TimeoutError) as exc:
        print(f'FAIL audit unavailable: {type(exc).__name__}', file=sys.stderr); return 2


if __name__ == '__main__': sys.exit(main())
