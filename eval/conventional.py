#!/usr/bin/env python3
"""Detector-only metrics. Aggregate output only; never updates the proxy ledger."""
import argparse
from collections import Counter
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bench'))
from common import sandbox_env  # noqa: E402

FIELDS = {'sms': 'text', 'url': 'url', 'indic': 'text', 'flow': 'features'}
DATA = Path('/var/tmp/arm-bharat-ai-soc-data/hidden')
DEFAULT = Path('/var/tmp/arm-bharat-ai-soc-work/evidence')


def metrics(gold, predictions):
    """Predictions missing or invalid count as errors in conservative metrics."""
    tp = fp = tn = fn = uncertain = invalid = 0
    positives = negatives = 0
    for ident, y in gold.items():
        if type(y) is not int or y not in (0, 1):
            raise ValueError('gold labels must be binary integers')
        positives += y == 1
        negatives += y == 0
        p = predictions.get(ident)
        if p == 'uncertain':
            uncertain += 1
        elif type(p) is not int or p not in (0, 1):
            invalid += 1
        elif y == 1 and p == 1: tp += 1
        elif y == 1: fn += 1
        elif p == 1: fp += 1
        else: tn += 1
    decided = tp + fp + tn + fn
    reasons = {}
    def rate(name, numerator, denominator):
        if not denominator:
            reasons[name] = 'zero denominator'
            return None
        return numerator / denominator
    def rates(prefix, t, f, n, miss):
        return {'precision': rate(prefix + '.precision', t, t + f),
                'recall': rate(prefix + '.recall', t, t + miss),
                'f1': rate(prefix + '.f1', 2*t, 2*t + f + miss),
                'fpr': rate(prefix + '.fpr', f, f + n)}
    missed_pos = positives - tp - fn
    missed_neg = negatives - fp - tn
    conditional = rates('conditional', tp, fp, tn, fn)
    conservative = rates('conservative', tp, fp + missed_neg, tn, fn + missed_pos)
    return {'n': len(gold), 'positives': positives, 'negatives': negatives,
            'decided': decided, 'uncertain': uncertain, 'invalid': invalid,
            'coverage': rate('coverage', decided, len(gold)),
            'confusion_decided': {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn},
            'conditional': conditional, 'conservative': conservative, 'undefined_reasons': reasons}


def read_rows(path):
    with path.open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(candidate, task, rows, visible=False):
    field = FIELDS[task]
    ids = [r['id'] for r in rows]
    gold = {r['id']: r['expect' if visible else 'label'] for r in rows}
    inputs = [{'id': r['id'], field: r['input' if visible else field]} for r in rows]
    with tempfile.TemporaryDirectory(prefix='conventional-', dir=DEFAULT) as temp:
        temp = Path(temp)
        inp, out, guard = temp / 'input.jsonl', temp / 'output.jsonl', temp / 'guard.log'
        inp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in inputs), encoding='utf-8')
        env = sandbox_env(guard)
        proc = subprocess.run([str(candidate / 'bin/predict'), '--task', 'sms' if task == 'indic' else task,
                               '--in', str(inp), '--out', str(out)], cwd=candidate, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
        if proc.returncode: raise RuntimeError(f'{task} detector failed with exit {proc.returncode}')
        if guard.exists() and guard.read_text().strip(): raise RuntimeError(f'{task} guard violation')
        preds = {}
        expected_counts, seen = Counter(ids), Counter()
        for row in (read_rows(out) if out.exists() else []):
            ident = row.get('id')
            seen[ident] += 1
            if seen[ident] > expected_counts[ident]: raise ValueError(f'{task} extra prediction ID')
            preds[ident] = row.get('label')
        result = metrics(gold, preds)
        result['input_rows'] = len(rows)
        result['duplicate_input_rows'] = len(rows) - len(gold)
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('candidate', type=Path)
    ap.add_argument('--out', type=Path, help='aggregate JSON output path (default: outside the repository)')
    ap.add_argument('--visible-only', action='store_true')
    args = ap.parse_args()
    candidate = args.candidate.resolve()
    DEFAULT.mkdir(parents=True, exist_ok=True)
    out = args.out or DEFAULT / ('conventional-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    if out.resolve().is_relative_to(ROOT): raise ValueError('output must be outside the repository')
    tasks = ('sms', 'url', 'flow') if args.visible_only else tuple(FIELDS)
    results = {}
    for task in tasks:
        source = ROOT / 'bench/fixtures' / f'{task}.jsonl' if args.visible_only else DATA / f'{task}_test.jsonl'
        results[task] = evaluate(candidate, task, read_rows(source), args.visible_only)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'candidate': candidate.name, 'visible_only': args.visible_only, 'tasks': results}, indent=2) + '\n')
    print(f'Aggregate metrics written to {out}')


if __name__ == '__main__': main()
