#!/usr/bin/env python3
"""Non-gating aggregate measurements on visible dev splits only."""
import argparse
from datetime import date
import json
from pathlib import Path
import resource
import sys
import time
from common import FIELDS, ROOT, predict, rows, valid_label
sys.path.insert(0,str(ROOT))
from eval.run_eval import det_metrics
from bench.baselines.keyword import label as keyword

def main():
    p=argparse.ArgumentParser(); p.add_argument('--cand',default='candidates/BEST'); p.add_argument('--baseline',choices=['keyword'],default='keyword'); p.add_argument('--data',required=True); p.add_argument('--output-prefix',default=None); a=p.parse_args()
    data_dir=Path(a.data).resolve()
    if data_dir.name != 'dev': raise ValueError('only a directory named dev is accepted')
    header='development split measurements (visible dev data; indic dev was used for tuning)'
    report={'title':header,'date':str(date.today()),'environment':'Arm cloud VM (Neoverse-N1)','candidate':str(a.cand),'tasks':{}}
    errors={}
    for task in ('sms','url','indic','flow'):
        try:
            dd={}; data=rows(data_dir/(task+'.jsonl'), dedupe=dd)
        except (ValueError, OSError) as exc:
            errors[task]=f'invalid input IDs or file ({type(exc).__name__})'
            print(f'BENCH {task}: FAIL invalid input IDs or file ({type(exc).__name__})',flush=True)
            continue
        if any(type(r.get('label')) is not int or r['label'] not in (0,1) for r in data): raise ValueError('invalid gold labels')
        gold={r['id']:r['label'] for r in data}
        field=FIELDS[task]
        try:
            pred, perf=predict(a.cand,task,[{'id':r['id'],field:r[field]} for r in data])
        except (ValueError, RuntimeError, KeyError) as exc:
            errors[task]=f'predict failed ({type(exc).__name__})'
            print(f'BENCH {task}: FAIL predict failed ({type(exc).__name__})',flush=True)
            continue
        invalid=sum(not valid_label(x) for x in pred.values())
        if invalid: raise ValueError(f'{task}: {invalid} invalid labels')
        metrics=det_metrics(gold,pred); metrics.update(perf,abstentions=sum(x=='uncertain' for x in pred.values()),d_score=metrics['score'])
        start=time.monotonic(); before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        bp={r['id']:keyword(task,r) for r in data}; bm=det_metrics(gold,bp); bm.update(wall_s=round(time.monotonic()-start,3),peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),abstentions=0,d_score=bm['score'],invalid=0)
        report['tasks'][task]={'BEST':metrics,'keyword':bm,'note':'tuning set, optimistic' if task=='indic' else 'visible dev','dedupe':dd}
        print(f"BENCH {task}: n={len(data)} BEST F1={metrics['f1']} D={metrics['d_score']} FPR={metrics['fpr']} abstentions={metrics['abstentions']} keyword F1={bm['f1']} D={bm['d_score']} FPR={bm['fpr']}",flush=True)
    report['errors']=errors
    out=Path(a.output_prefix) if a.output_prefix else ROOT/'bench/results'/('oracle-a1-'+str(date.today()))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# '+header,'','Arm cloud VM (Neoverse-N1); visible dev data only. Indic was used for tuning; its numbers are optimistic.','', '| Task | Model | n | F1 | Precision | Recall | FPR | Abstentions | Invalid | D-score | Wall s | Peak RSS MB |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for task,items in report['tasks'].items():
        for model in ('BEST','keyword'):
            m=items[model]; lines.append(f"| {task} | {model} | {m['n']} | {m['f1']} | {m['precision']} | {m['recall']} | {m['fpr']} | {m['abstentions']} | {m['invalid']} | {m['d_score']} | {m['wall_s']} | {m['peak_rss_mb']} |")
    for task,why in errors.items(): lines.append(f'| {task} | unavailable: {why} | | | | | | | | | | |')
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print('BENCH '+('FAIL' if errors else 'PASS')+' (aggregate reports written)')
    return 1 if errors else 0
if __name__=='__main__': sys.exit(main())
