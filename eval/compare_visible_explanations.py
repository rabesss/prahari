#!/usr/bin/env python3
"""Compare read_explain.py outputs on project-authored visible cases, never hidden outputs."""
import argparse
import json
from pathlib import Path
from consistency_v2 import consistent as consistent_v2
from run_eval import consistent as proxy_consistent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    def load(path):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        d = {r['case']: r for r in rows}
        if len(rows) != len(d): raise ValueError('duplicate case')
        return d
    before, after = load(a.baseline), load(a.candidate)
    if set(before) != set(after): raise ValueError('case sets differ')
    result = {'n': len(before), 'baseline': {'proxy': 0, 'consistency_v2': 0},
              'candidate': {'proxy': 0, 'consistency_v2': 0}, 'cases': []}
    for key in sorted(before):
        b, c = before[key], after[key]
        if b['expected'] != c['expected']: raise ValueError('expected labels differ')
        for name, row in (('baseline', b), ('candidate', c)):
            y, text = row['expected'], row['explanation']
            result[name]['proxy'] += proxy_consistent(y, text.lower())
            result[name]['consistency_v2'] += consistent_v2(y, text)
        result['cases'].append({'case': key, 'baseline': b['explanation'], 'candidate': c['explanation']})
    root = Path(__file__).resolve().parents[1]
    if a.out.resolve().is_relative_to(root): raise ValueError('output must be outside repository')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('visible explanation comparison:', {k: v for k, v in result.items() if k != 'cases'})
    print('per-item visible comparison:', a.out)


if __name__ == '__main__': main()
