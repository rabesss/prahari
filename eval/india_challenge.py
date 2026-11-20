#!/usr/bin/env python3
"""Run the project-authored challenge, keeping SMS and injection results separate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from conventional import metrics

KEYS = {'id', 'text', 'lang', 'label', 'category', 'pair_id', 'route'}
LABELS = {'benign': 0, 'malicious': 1}
CHALLENGE_SHA256 = '135222ee67a84cca28252df6207c5d62fcefeb313755bc000e0d7b979e095a67'


def load(path, *, expected_sha256=None):
    data = path.read_bytes()
    expected = CHALLENGE_SHA256 if expected_sha256 is None else expected_sha256
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('dataset sha256 mismatch')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate key')
            result[key] = value
        return result
    rows = [json.loads(line, object_pairs_hook=pairs) for line in data.decode('utf-8').splitlines() if line.strip()]
    if not rows or any(not isinstance(r, dict) or set(r) != KEYS for r in rows):
        raise ValueError('invalid challenge schema')
    ids = [r['id'] for r in rows]
    if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('invalid or duplicate challenge IDs')
    if len(rows) > 500 or any(r['route'] not in ('sms', 'injection') or r['label'] not in ('benign', 'malicious') or
           r['lang'] not in ('en', 'hi', 'hinglish') or not (r['pair_id'] is None or isinstance(r['pair_id'], str)) or
           any(not isinstance(r[k], str) or not r[k] for k in ('text', 'lang', 'category')) for r in rows):
        raise ValueError('invalid challenge values')
    return rows


def summarize(rows, predictions):
    sms = [r for r in rows if r['route'] == 'sms']
    def calc(subset):
        return metrics({r['id']: LABELS[r['label']] for r in subset},
                       {r['id']: predictions[r['id']]['label'] for r in subset})
    return {'sms': calc(sms),
            'languages': {k: calc([r for r in sms if r['lang'] == k]) for k in sorted({r['lang'] for r in sms})},
            'categories': {k: calc([r for r in sms if r['category'] == k]) for k in sorted({r['category'] for r in sms})},
            'injection': calc([r for r in rows if r['route'] == 'injection'])}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('challenge', type=Path)
    p.add_argument('--sample', type=Path, help='IDs to explain once')
    p.add_argument('--out', type=Path, help='write item results outside the repository')
    a = p.parse_args()
    rows = load(a.challenge)
    sample = a.sample.read_text().splitlines() if a.sample else []
    if len(sample) != len(set(sample)) or not set(sample) <= {r['id'] for r in rows}:
        raise ValueError('invalid explanation sample')
    if a.out and a.out.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('output must be outside repository')
    sys.path.insert(0, str(a.candidate.resolve()))
    from triage.detect import predict_text, classify_any
    sms = [r for r in rows if r['route'] == 'sms']
    sms_preds = predict_text([r['text'] for r in sms])
    predictions = {r['id']: {'label': lab, 'score': float(score), 'evidence': ev}
                   for r, (lab, score, ev) in zip(sms, sms_preds, strict=True)}
    for r in rows:
        if r['route'] == 'injection':
            lab, score, ev = classify_any('injection', r['text'])
            predictions[r['id']] = {'label': lab, 'score': float(score), 'evidence': ev}
    result = {'summary': summarize(rows, predictions), 'predictions': predictions, 'explanations': {}}
    def save():
        if a.out:
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    if sample:
        from triage.llm import Explainer
        ex = Explainer()
        by_id = {r['id']: r for r in rows}
        for ident in sample:
            r, pred = by_id[ident], predictions[ident]
            try:
                explanation, stats = ex.generate(ex.prompt(r['route'], r['text'], pred['label'], pred['evidence']))
                if not isinstance(explanation, str) or not explanation.strip():
                    raise ValueError('empty explanation')
                result['explanations'][ident] = {'text': explanation, 'stats': stats, 'explanation_status': 'success'}
            except ValueError:
                result['explanations'][ident] = {'explanation_status': 'failed', 'explanation_error': 'Explanation unavailable.'}
            save()
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
