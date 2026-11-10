#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from common import ROOT, digest, predict, stable_ids

SUITES = sorted((ROOT / 'research/stress').glob('*.jsonl'))

def load(path):
    with open(path, encoding='utf-8') as f: return stable_ids([json.loads(x) for x in f if x.strip()])

def evaluate(data, predictions):
    return {r['id']: {'label': r['label'], 'prediction': predictions[r['id']], 'correct': type(predictions[r['id']]) is int and predictions[r['id']] == r['label']} for r in data}

def main():
    p=argparse.ArgumentParser(); p.add_argument('candidate', nargs='?', default='candidates/BEST'); p.add_argument('--reference', default=str(ROOT/'bench/reference.json')); p.add_argument('--record', action='store_true'); a=p.parse_args()
    reference = {} if a.record else json.loads(Path(a.reference).read_text())['stress']
    result = {}; failures = []
    for path in SUITES:
        data=load(path); pred, stats=predict(a.candidate, 'sms', [{'id':r['id'],'text':r['text']} for r in data]); scores=evaluate(data,pred)
        entry={'sha256':digest(path),'n':len(data),'rows':{k:{**v,'gate':v['correct']} for k,v in scores.items()}}
        result[path.name]=entry
        if not a.record:
            ref=reference.get(path.name, {})
            if ref.get('sha256') != entry['sha256'] or ref.get('n') != len(data) or set(ref.get('rows',{})) != set(scores): failures.append(f'{path.name}: regenerate reference')
            else:
                for k,v in scores.items():
                    old=ref['rows'][k]
                    if old['label'] != v['label']: failures.append(f'{path.name}/{k}: label changed')
                    if old.get('gate') and old.get('correct') and not v['correct']: failures.append(f'{path.name}/{k}: regression')
        print(f"STRESS {path.name}: correct={sum(v['correct'] for v in scores.values())}/{len(data)} benign={sum(v['correct'] and v['label']==0 for v in scores.values())}/{sum(v['label']==0 for v in scores.values())} malicious={sum(v['correct'] and v['label']==1 for v in scores.values())}/{sum(v['label']==1 for v in scores.values())} abstentions={sum(v['prediction']=='uncertain' for v in scores.values())} invalid={stats['invalid']}")
        if stats['invalid']: failures.append(f'{path.name}: invalid predictions')
    if not a.record and set(reference) != {p.name for p in SUITES}: failures.append('stress suites changed: regenerate reference')
    for error in failures: print('FAIL',error)
    if a.record: print('STRESS_JSON '+json.dumps(result, ensure_ascii=False))
    print('STRESS '+('FAIL' if failures else 'PASS')); return bool(failures)

if __name__ == '__main__': sys.exit(main())
