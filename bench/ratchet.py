#!/usr/bin/env python3
"""Reference ratchet: a row that gated at <base> must still gate in the working-tree bench/reference.json.

A regenerated reference could otherwise silently ungate rows in the same change that breaks them. A relabelled row (changed expect/label)
also counts as a downgrade. A downgrade is
allowed only when bench/accepted_downgrades.json gains an entry for it in this range (entries already present at
<base> do not count again), so every downgrade is a reviewable diff line.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REF = 'bench/reference.json'
ACCEPTED = 'bench/accepted_downgrades.json'
root = ROOT


def at(ref, path):
    run = subprocess.run(['git', 'show', f'{ref}:{path}'], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return json.loads(run.stdout) if run.returncode == 0 else None


def accepted(value):
    if value is None: return set()
    entries = value.get('downgrades') if isinstance(value, dict) else None
    if not isinstance(entries, list): raise ValueError('accepted_downgrades.json: expected {"downgrades": [...]}')
    out = set()
    for e in entries:
        if not isinstance(e, dict) or not all(isinstance(e.get(k), str) and e[k] for k in ('suite', 'file', 'row', 'reason')):
            raise ValueError('accepted_downgrades.json: each entry needs suite, file, row and a non-empty reason')
        out.add((e['suite'], e['file'], e['row']))
    return out


def gated(reference):
    """{(suite, file, row): expectation} for every gating row; a changed expectation counts as a downgrade.
    A stress row gates only while it is also correct (bench/stress.py), so its expectation includes that flag."""
    out = {}
    for suite, key in (('fixtures', 'expect'), ('stress', 'label')):
        for name, entry in (reference or {}).get(suite, {}).items():
            for row, v in entry.get('rows', {}).items():
                if v.get('gate'): out[(suite, name, row)] = (v.get(key), bool(v.get('correct'))) if suite == 'stress' else v.get(key)
    return out


def main():
    global root
    p = argparse.ArgumentParser(); p.add_argument('base'); p.add_argument('--root', default=str(ROOT)); a = p.parse_args()
    root = Path(a.root)
    if subprocess.run(['git', 'rev-parse', '--verify', a.base + '^{commit}'], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        print('RATCHET FAIL: base commit unavailable'); return 1
    old = at(a.base, REF)
    if old is None:
        print('RATCHET PASS: no reference at base'); return 0
    new = json.loads((root / REF).read_text())
    path = root / ACCEPTED
    allowed = accepted(json.loads(path.read_text()) if path.exists() else None) - accepted(at(a.base, ACCEPTED))
    before, after = gated(old), gated(new)
    lost = sorted(k for k, expect in before.items() if k not in after or after[k] != expect)
    failures = [x for x in lost if x not in allowed]
    for suite, name, row in lost:
        print(f"RATCHET {'accepted' if (suite, name, row) in allowed else 'FAIL'} downgrade {suite}/{name}/{row}")
    print(f"RATCHET {'FAIL' if failures else 'PASS'}: {len(before)} gated at base, {len(after)} now, {len(lost)} downgraded")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
