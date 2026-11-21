"""Candidate-side India route adapter. Input and predictions remain private."""
import json
import sys
from pathlib import Path

candidate, source, dest = map(Path, sys.argv[1:])
sys.path.insert(0, str(candidate))
from triage.detect import classify_any, predict_text

rows = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines() if line.strip()]
sms = [r for r in rows if r['route'] == 'sms']
results = {r['id']: label for r, (label, _, _) in zip(sms, predict_text([r['text'] for r in sms]), strict=True)}
for row in rows:
    if row['route'] == 'injection':
        results[row['id']] = classify_any('injection', row['text'])[0]
dest.write_text(''.join(json.dumps({'id': k, 'label': v}) + '\n' for k, v in results.items()))
