#!/usr/bin/env python3
"""Inspect every added or modified blob and every commit message in a complete, ancestral Git range.

The allowlist is the gate. --hidden-check is a controller-only supplementary scan for verbatim hidden items and
visible third-party dataset texts; it is not a disclosure proof.
"""
import argparse
from collections import deque
import json
import math
import os
import re
import signal
import subprocess
import sys
import zlib
from pathlib import Path

# Code and docs only under known project roots or at the top level; never under data/.
ROOTS = r'(?:candidates|research|bench|docs|eval|bin|models)/'
CODE = re.compile(r'(?:' + ROOTS + r'(?:[^/]+/)*)?[^/]+\.(?:py|sh|md|toml|cfg|html|css|js)'
                  r'|(?:' + ROOTS + r'(?:[^/]+/)*)?requirements[^/]*\.txt'
                  r'|(?:' + ROOTS + r'(?:[^/]+/)*)?\.gitignore'
                  r'|bin/[^/]+|candidates/[^/]+/bin/[^/]+|\.github/workflows/[^/]+\.yml')
CONFIG = re.compile(r'candidates/[^/]+/config\.json|models/registry\.json|eval/weights\.json|bench/[^/]+\.json')
ARTIFACT = re.compile(r'candidates/[^/]+/artifacts/[^/]+\.joblib')
RECORD = re.compile(r'research/evals/[^/]+/(?:summary|details)\.json')
LOG = re.compile(r'research/evals/[^/]+/(?:run|app|tests|guard)\.log')
RESULT = re.compile(r'bench/results/[^/]+\.json')
SYNTH = re.compile(r'(?:research/stress|bench/fixtures)/[^/]+\.jsonl')
# (allowed keys, required keys) per synthetic directory.
SYNTH_KEYS = {'research/stress': ({'id', 'label', 'text'}, {'label', 'text'}),
              'bench/fixtures': ({'id', 'input', 'expect', 'rationale'}, {'id', 'input', 'expect', 'rationale'})}
# Paths owned by the controller: printed for review on every audit (integrity, not disclosure).
CONTROLLER = re.compile(r'bin/eval|eval/.*|models/registry\.json|bench/.*|\.github/.*')
# Hidden/visible split ids: hex-suffixed sms/url ids, flow test rows, explain set X-NN and Indian set B B-NNNN
# (the last two case-sensitive: lowercased model vocabularies hold n-grams such as x-20).
ITEM_ID = re.compile(r'\b(?:sms|url|flow|ind|indic|ex|exp)[-_][0-9a-f]{6,}\b|\bflow-te-\d+\b|(?-i:\bX-\d{2}\b|\bB-\d{4}\b)', re.I)
# Constructed so that this source holds no token-shaped example. Matches are never printed.
SECRET = re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b'
                    rb'|\bhf_[A-Za-z0-9]{20,}\b|\bsk-[A-Za-z0-9_-]{20,}\b|\bglpat-[A-Za-z0-9_-]{20,}\b|\bxox[abprs]-[A-Za-z0-9-]{10,}'
                    rb'|-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\bpassword\s*[:=]\s*["\']?[^\s"\']{4,}'
                    rb'|(?:api[_-]?key|secret|token|access[_-]?key)["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-/+=]{16,}["\']', re.I)
NUM = r'\d+(?:\.\d+)?'
PYTEST_COUNTS = r'\d+ (?:passed|failed|skipped|errors?|warnings?|deselected|xfailed|xpassed)'
STATUS = [re.compile(p) for p in (
    r'== (?:predict --task (?:sms|url|flow)|explain --in) rc=-?\d+ timeout=(?:True|False) wall_s=' + NUM + ' peak_rss_mb=' + NUM + r'\s*',
    r'=+ ' + PYTEST_COUNTS + r'(?:, ' + PYTEST_COUNTS + r')* in ' + NUM + r's(?: \(\d+:\d\d:\d\d\))? =+\s*',
    r'[.sxEF]+\s+\[\s*\d+%\]\s*',
    PYTEST_COUNTS + r'(?:, ' + PYTEST_COUNTS + r')* in ' + NUM + r's\s*',
    r'(?:SELFTEST|selftest)\s*(?::|=)?\s*OK\s*',
)]
# Data-shaped lines inside code/docs: JSON records with dataset keys, or wide CSV rows.
DATA_LINE = re.compile(r'^\s*[\[{].*"(?:label|text|url|features|attack|input)"\s*:|^[^\s,()\[\]{}=]*(?:,[^,()\[\]{}=\n]*){9,}$', re.M)
DATA_LINE_LIMIT = 20
MAX_INT = 2 ** 53
MAX_LEAVES = 5000
MAX_MESSAGE = 8000
MAX_INFLATE = 64_000_000
SELFTEST_KEYS = {'verdict', 'score', 'evidence'}


def strict_pairs(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate key')
    return dict(pairs)


def loads(text):
    def reject(x): raise ValueError(x)
    return json.loads(text, parse_constant=reject, object_pairs_hook=strict_pairs)


def number_ok(v):
    if type(v) is int: return abs(v) < MAX_INT
    if type(v) is float: return math.isfinite(v)
    return False


def selftest_line(line):
    """bin/app --selftest prints one JSON list of results for the presets hard-coded in candidates/*/app/server.py."""
    try:
        value = loads(line)
    except (ValueError, RecursionError):
        return False
    if not isinstance(value, list) or not 1 <= len(value) <= 5:
        return False
    for r in value:
        if not isinstance(r, dict) or not set(r) <= SELFTEST_KEYS or r.get('verdict') not in ('malicious', 'benign', 'uncertain'):
            return False
        if not number_ok(r.get('score')) or not 0 <= r['score'] <= 1:
            return False
        ev = r.get('evidence', [])
        if not isinstance(ev, list) or len(ev) > 10 or any(not isinstance(e, str) or len(e) > 200 or ITEM_ID.search(e) for e in ev):
            return False
    return True


def git(*args, binary=False):
    result = subprocess.run(['git', '--no-replace-objects', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout if binary else result.stdout.decode('utf-8', 'strict').strip()


def json_ok(value, budget):
    """Scalar leaves only: bounded numbers, booleans, null, short strings without item ids; short arrays, no arrays
    of arrays; a total leaf budget per document."""
    budget[0] -= 1
    if budget[0] < 0: return False
    if value is None or type(value) is bool: return True
    if type(value) in (int, float): return number_ok(value)
    if isinstance(value, str): return len(value) <= 200 and not ITEM_ID.search(value)
    if isinstance(value, list):
        return len(value) <= 50 and not any(isinstance(x, list) for x in value) and all(json_ok(x, budget) for x in value)
    if isinstance(value, dict):
        return all(len(k) <= 200 and not ITEM_ID.search(k) and json_ok(v, budget) for k, v in value.items())
    return False


def valid_json(data, lines=False):
    try:
        text = data.decode('utf-8')
        values = [loads(x) for x in text.splitlines() if x.strip()] if lines else [loads(text)]
        return bool(values) and all(json_ok(x, [MAX_LEAVES]) for x in values)
    except (ValueError, UnicodeError, RecursionError):
        return False


def config_ok(data):
    """Config JSON: parses strictly, numbers bounded, no item ids anywhere, no data-shaped content."""
    try:
        text = data.decode('utf-8'); value = loads(text)
    except (ValueError, UnicodeError, RecursionError):
        return False
    def walk(v):
        if isinstance(v, dict): return all(not ITEM_ID.search(k) and walk(x) for k, x in v.items())
        if isinstance(v, list): return all(walk(x) for x in v)
        if isinstance(v, str): return not ITEM_ID.search(v)
        return v is None or type(v) is bool or number_ok(v)
    return walk(value)


def synth_ok(path, data):
    allowed, required = SYNTH_KEYS[path.rsplit('/', 1)[0]]
    try:
        rows = [loads(x) for x in data.decode('utf-8').splitlines() if x.strip()]
    except (ValueError, UnicodeError, RecursionError):
        return False
    return 0 < len(rows) <= 500 and all(isinstance(r, dict) and required <= set(r) <= allowed and not ITEM_ID.search(str(r.get('id', ''))) for r in rows)


def json_strings(data):
    """Decoded string values of a JSON or JSONL blob (catches \\u-escaped text), or '' if it does not parse."""
    out = []
    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items(): out.append(k); walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, str): out.append(v)
        else: out.append(str(v))
    try:
        for line in data.decode('utf-8').splitlines():
            if line.strip(): walk(json.loads(line))
    except (ValueError, UnicodeError, RecursionError):
        try: walk(json.loads(data))
        except (ValueError, UnicodeError, RecursionError): return ''
    return '\n'.join(out)


def inflate(data):
    """joblib files here are zlib streams; return the decompressed bytes, or the raw bytes if not zlib."""
    if data[:1] != b'\x78':
        return data
    d = zlib.decompressobj()
    out = d.decompress(data, MAX_INFLATE)
    if d.unconsumed_tail: raise ValueError('artifact inflates beyond limit')
    return out


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


HIDDEN = Path('/var/tmp/arm-bharat-ai-soc-data/hidden')
HIDDEN_FILES = ('sms_test.jsonl', 'url_test.jsonl', 'indic_test.jsonl', 'flow_test.jsonl', 'explain_set.jsonl')
# dev/explain_examples.jsonl is written by eval/prep_data.py itself (project text), so it is not a third-party corpus.
VISIBLE_FILES = ('train/sms.jsonl', 'train/url.jsonl', 'train/indic.jsonl', 'train/indic_seed.jsonl',
                 'dev/sms.jsonl', 'dev/url.jsonl', 'dev/indic.jsonl')
# Reviewed blobs that quote visible dataset texts (never hidden content); read from this script's own checkout.
ALLOW = Path(__file__).resolve().parent / 'hidden_check_allow.json'


def visible_allowed():
    if not ALLOW.exists(): return set()
    value = loads(ALLOW.read_text(encoding='utf-8'))
    entries = value.get('visible_text_blobs') if isinstance(value, dict) else None
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not re.fullmatch(r'[0-9a-f]{40}', str(e.get('blob')))
                                            or not isinstance(e.get('reason'), str) or not e['reason'] for e in entries):
        raise ValueError('hidden_check_allow.json malformed')
    return {e['blob'] for e in entries}


def corpus_matchers(data_root):
    """Only invoked by the controller. Returns (hidden ids, hidden texts, visible third-party texts) matchers; texts
    are >= 25 normalised chars. Flow rows are numeric NSL-KDD records and are covered by the path and data-shape
    rules. Missing or malformed input fails closed."""
    if any(not (HIDDEN / name).is_file() for name in HIDDEN_FILES):
        raise ValueError('hidden check input unavailable')
    visible = [data_root / name for name in VISIBLE_FILES]
    if any(not path.is_file() for path in visible):
        raise ValueError('visible data input unavailable')
    ids, texts, vtexts = set(), set(), set()
    for path in [HIDDEN / name for name in HIDDEN_FILES] + visible:
        hidden = path.parent == HIDDEN
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            if hidden and (not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']):
                raise ValueError('hidden check input malformed')
            # Short ids (X-NN, B-NNNN) collide with n-gram vocabularies as substrings; ITEM_ID covers them case-sensitively.
            if hidden and len(row['id']) >= 10: ids.add(row['id'].lower())
            for key in ('text', 'url', 'input'):
                if isinstance(row.get(key), str):
                    value = norm(row[key])
                    if len(value) >= 25: (texts if hidden else vtexts).add(value)
    if not ids or not texts or not vtexts: raise ValueError('hidden check input incomplete')
    return Matcher(ids), Matcher(texts), Matcher(vtexts)


def main():
    p = argparse.ArgumentParser(); p.add_argument('base'); p.add_argument('sha'); p.add_argument('--hidden-check', action='store_true')
    p.add_argument('--data-root', default=str(Path.home() / 'projects/arm-bharat-ai-soc/data'), help='visible data root for --hidden-check')
    args = p.parse_args()
    try:
        if git('rev-parse', '--is-shallow-repository') != 'false': raise ValueError('shallow history')
        base = git('rev-parse', '--verify', args.base + '^{commit}')
        head = git('rev-parse', '--verify', args.sha + '^{commit}')
        anc = subprocess.run(['git', '--no-replace-objects', 'merge-base', '--is-ancestor', base, head], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if anc.returncode == 1:
            print('FAIL audit unavailable: base is not an ancestor of sha (rewritten or unrelated history)', file=sys.stderr); return 2
        if anc.returncode != 0: raise ValueError('ancestor check failed')
        commits = git('rev-list', '--topo-order', f'{base}..{head}').splitlines()
        if args.hidden_check:
            def timeout(_signum, _frame): raise TimeoutError('hidden check exceeded 10 minutes')
            signal.signal(signal.SIGALRM, timeout); signal.alarm(600)
            os.nice(10)
            id_matcher, text_matcher, visible_matcher = corpus_matchers(Path(args.data_root))
            allowed = visible_allowed()
            def corpus_hit(text, oid=None):
                """Rule name for a hidden or (unreviewed) visible dataset match, else None."""
                n = norm(text)
                if id_matcher.contains(text.lower()) or text_matcher.contains(n): return 'hidden content match'
                if visible_matcher.contains(n): return None if oid in allowed else f'visible dataset text match (blob={oid})'
                return None
        else: print('hidden check SKIPPED (allowlist mode)')
        failures = set(); artifacts = set(); controller = set(); seen = set(); blob_cache = {}; hidden_hits = set()
        for commit in commits:
            message = git('cat-file', 'commit', commit, binary=True).split(b'\n\n', 1)[-1]
            label = f'<commit message {commit[:12]}>'
            if len(message) > MAX_MESSAGE: failures.add((label, 'message size limit'))
            if SECRET.search(message): failures.add((label, 'secret pattern'))
            try: text = message.decode('utf-8')
            except UnicodeError: failures.add((label, 'undecodable message')); text = ''
            if ITEM_ID.search(text) or len(DATA_LINE.findall(text)) >= 3: failures.add((label, 'item id or data-shaped message'))
            hit = args.hidden_check and text and corpus_hit(text)
            if hit: hidden_hits.add(label); failures.add((label, hit))
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
                if CONTROLLER.fullmatch(path): controller.add(path)
                rules = [('code/docs', CODE.fullmatch(path)), ('config', CONFIG.fullmatch(path)), ('artifact', ARTIFACT.fullmatch(path)),
                         ('eval JSON', RECORD.fullmatch(path) or RESULT.fullmatch(path)), ('eval log', LOG.fullmatch(path)),
                         ('ledger', path == 'research/evals/ledger.jsonl'), ('synthetic', SYNTH.fullmatch(path))]
                matched = [name for name, match in rules if match]
                if len(matched) != 1:
                    fail('path not uniquely allowlisted'); continue
                rule = matched[0]
                size = int(git('cat-file', '-s', oid))
                limit = {'code/docs': 1_000_000, 'config': 256_000, 'artifact': 5_000_000, 'eval log': 4_000, 'eval JSON': 1_000_000, 'ledger': 1_000_000, 'synthetic': 1_000_000}[rule]
                if size > limit: fail(f'{rule} size limit'); continue
                if oid not in blob_cache: blob_cache[oid] = git('cat-file', 'blob', oid, binary=True)
                data = blob_cache[oid]
                if rule == 'artifact':
                    artifacts.add((path, oid, size))
                    try: data = inflate(data)
                    except (ValueError, zlib.error): fail('artifact undecodable'); continue
                    if ITEM_ID.search(data.decode('latin-1')): fail('item id in artifact')
                    hit = args.hidden_check and corpus_hit(data.decode('utf-8', 'replace'), oid)
                    if hit: hidden_hits.add(path); fail(hit)
                    continue
                if SECRET.search(data): fail('secret pattern')
                if rule in ('eval JSON', 'ledger') and not valid_json(data, rule == 'ledger'): fail('eval JSON leaf/array/id policy')
                if rule == 'config' and not config_ok(data): fail('config JSON policy')
                if rule == 'synthetic' and not synth_ok(path, data): fail('synthetic schema policy')
                if rule == 'code/docs':
                    try: text = data.decode('utf-8')
                    except UnicodeError: fail('undecodable code/docs'); continue
                    if len(DATA_LINE.findall(text)) >= DATA_LINE_LIMIT: fail('data-shaped code/docs content')
                if rule == 'eval log':
                    try: lines = data.decode('utf-8').splitlines()
                    except UnicodeError: lines = ['<invalid>']
                    is_app = path.endswith('/app.log')
                    if any(not (any(rx.fullmatch(line) for rx in STATUS) or (is_app and selftest_line(line))) for line in lines): fail('non-status log line')
                if args.hidden_check:
                    try: decoded = data.decode('utf-8')
                    except UnicodeError: fail('hidden check undecodable text'); continue
                    extra = json_strings(data) if path.endswith(('.json', '.jsonl')) else ''
                    hit = corpus_hit(decoded, oid) or (extra and corpus_hit(extra, oid))
                    if hit: hidden_hits.add(path); fail(hit)
        for path, oid, size in sorted(artifacts): print(f'ARTIFACT {path} blob={oid} bytes={size}')
        for path in sorted(controller): print(f'CONTROLLER-OWNED changed (review): {path}')
        for path, rule in sorted(failures): print(f'FAIL {path}: {rule}')
        if args.hidden_check: print(f'hidden check: {len(hidden_hits)} matched paths')
        print(f'audited {base}..{head}: {len(commits)} commits, {len(seen)} path/blob entries; {len(failures)} failure(s)')
        return 1 if failures else 0
    except (subprocess.CalledProcessError, ValueError, OSError, UnicodeError, TimeoutError) as exc:
        print(f'FAIL audit unavailable: {type(exc).__name__}', file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())
