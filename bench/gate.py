#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from common import ROOT, digest, fixture_inputs, predict, rows

FIXTURES=sorted((ROOT/'bench/fixtures').glob('*.jsonl'))
CHALLENGE = ROOT / 'bench/challenge/india_challenge_v1.jsonl'
CHALLENGE_SHA256 = '135222ee67a84cca28252df6207c5d62fcefeb313755bc000e0d7b979e095a67'

def main():
    p=argparse.ArgumentParser(); p.add_argument('candidate', nargs='?', default='candidates/BEST'); p.add_argument('--reference', default=str(ROOT/'bench/reference.json')); p.add_argument('--record',action='store_true'); a=p.parse_args()
    if not CHALLENGE.is_file() or digest(CHALLENGE) != CHALLENGE_SHA256:
        print('FAIL frozen challenge sha256 mismatch or missing'); return 1
    for artifact in sorted((Path(a.candidate)/'artifacts').glob('*.joblib')): print(f'ARTIFACT {artifact.name}: bytes={artifact.stat().st_size}')
    reference={} if a.record else json.loads(Path(a.reference).read_text())['fixtures']; result={}; failures=[]
    for path in FIXTURES:
        task=path.stem; data=rows(path)
        if any(type(r.get('expect')) not in (int,str) or r['expect'] not in (0,1,'any') or not isinstance(r.get('rationale'),str) for r in data): raise ValueError('invalid fixture')
        pred, stats=predict(a.candidate,task,fixture_inputs(task,data)); entries={}
        for row in data:
            k=row['id']; want=row['expect']; got=pred[k]; correct=type(got) is int and got == want
            entries[k]={'expect':want,'prediction':got,'gate':want != 'any' and correct}
        entry={'sha256':digest(path),'n':len(data),'rows':entries}; result[path.name]=entry
        if not a.record:
            ref=reference.get(path.name,{})
            if ref.get('sha256')!=entry['sha256'] or ref.get('n')!=len(data) or set(ref.get('rows',{}))!=set(entries): failures.append(f'{path.name}: regenerate reference')
            else:
                for k,v in entries.items():
                    old=ref['rows'][k]
                    if old.get('expect')!=v['expect']: failures.append(f'{path.name}/{k}: regenerate reference')
                    if old.get('gate') and (v['expect']=='any' or not (type(v['prediction']) is int and v['prediction']==v['expect'])): failures.append(f'{path.name}/{k}: regression')
        wrong=[f"{k}(expected={v['expect']},got={v['prediction']})" for k,v in entries.items() if v['expect']!='any' and not (type(v['prediction']) is int and v['prediction']==v['expect'])]
        print(f"FIXTURES {path.name}: matched={sum(v['gate'] for v in entries.values())}/{len(data)} abstentions={sum(v['prediction']=='uncertain' for v in entries.values())} invalid={stats['invalid']} wall_s={stats['wall_s']} peak_rss_mb={stats['peak_rss_mb']}")
        for x in wrong:
            row_id=x.split('(',1)[0]
            gated=not a.record and reference.get(path.name,{}).get('rows',{}).get(row_id,{}).get('gate',False)
            print(('GATED disagreement' if gated else 'REPORT ONLY disagreement'),x)
        if stats['invalid']: failures.append(f'{path.name}: invalid predictions')
    if not a.record and set(reference)!={p.name for p in FIXTURES}: failures.append('fixture files changed: regenerate reference')
    for error in failures: print('FAIL',error)
    if a.record: print('FIXTURE_JSON '+json.dumps(result, ensure_ascii=False))
    print('FIXTURES '+('FAIL' if failures else 'PASS')); return 1 if failures else 0

if __name__=='__main__': sys.exit(main())
