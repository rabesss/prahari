"""Shared strict JSONL prediction adapter."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

def rows(path, dedupe=None):
    """Strict by default. With dedupe={} (a stats dict), rows sharing an id and label keep the first copy and
    ids with conflicting labels are dropped; counts are recorded in the dict (dev data quirk, e.g. repeated URLs)."""
    with open(path, encoding='utf-8') as f:
        result = [json.loads(line) for line in f if line.strip()]
    if not result: raise ValueError(f'empty input: {path}')
    ids = [r.get('id') for r in result]
    if any(not isinstance(i, str) or not i for i in ids): raise ValueError(f'missing input ids: {path}')
    if len(set(ids)) != len(ids):
        if dedupe is None: raise ValueError(f'duplicate input ids: {path}')
        labels = {}
        for r in result: labels.setdefault(r['id'], set()).add(json.dumps(r.get('label')))
        conflict = {i for i, s in labels.items() if len(s) > 1}
        seen, kept = set(), []
        for r in result:
            if r['id'] in conflict or r['id'] in seen: continue
            seen.add(r['id']); kept.append(r)
        dedupe.update(duplicates_dropped=len(result) - len(kept) - sum(ids.count(i) for i in conflict), conflicting_ids_dropped=len(conflict))
        result = kept
    return result

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def valid_label(value): return type(value) is int and value in (0, 1) or value == 'uncertain' and isinstance(value, str)

def predict(cand, task, input_rows):
    ids = [r['id'] for r in input_rows]
    if len(ids) != len(set(ids)): raise ValueError('duplicate input ids')
    with tempfile.TemporaryDirectory(prefix='.bench-', dir=ROOT) as temp:
        inp, out, timing = (Path(temp) / x for x in ('in.jsonl','out.jsonl','time.txt'))
        inp.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in input_rows), encoding='utf-8')
        cmd = [str(Path(cand).resolve() / 'bin/predict'), '--task', 'sms' if task == 'indic' else task, '--in', str(inp), '--out', str(out)]
        start = time.monotonic()
        subprocess.run(['/usr/bin/time','-f','%M','-o',str(timing),*cmd], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wall = time.monotonic() - start
        predictions = rows(out)
        mapped = {r['id']: r.get('label') for r in predictions}
        if set(mapped) != set(ids) or len(predictions) != len(ids): raise ValueError('prediction IDs do not equal input IDs')
        invalid = sum(not valid_label(v) for v in mapped.values())
        return mapped, {'wall_s': round(wall, 3), 'peak_rss_mb': round(int(timing.read_text().strip()) / 1024, 1), 'invalid': invalid}

def fixture_inputs(task, data):
    field = {'sms':'text','url':'url','flow':'features'}[task]
    return [{'id':r['id'], field:r['input']} for r in data]

def stable_ids(data):
    out = []
    for row in data:
        r = dict(row)
        if not r.get('id'): r['id'] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()
        out.append(r)
    ids = [r['id'] for r in out]
    if len(set(ids)) != len(ids): raise ValueError('duplicate stress row IDs')
    return out
