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
        conflicting_rows = sum(ids.count(i) for i in conflict)
        dedupe.update(duplicates_dropped=len(result) - len(kept) - conflicting_rows, conflicting_ids_dropped=len(conflict),
                      conflicting_rows_dropped=conflicting_rows)
        result = kept
    return result

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def valid_label(value): return (type(value) is int and value in (0, 1)) or (isinstance(value, str) and value == 'uncertain')

DATA = Path('/var/tmp/arm-bharat-ai-soc-data')
EVROOT = Path('/var/tmp/arm-bharat-ai-soc-eval')
FIELDS = {'sms': 'text', 'indic': 'text', 'url': 'url', 'flow': 'features'}
TIMEOUT_S = 900

def sandbox_env(guard_log):
    """Mirror bin/eval: no cloud/GitHub credentials, offline guard, loopback-only proxies, hidden paths denied."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(('BOXD', 'SAIL', 'OPENAI', 'ANTHROPIC', 'GH_', 'GITHUB'))}
    env.update({
        'PYTHONPATH': str(ROOT / 'eval' / 'guard'), 'HC_GUARD_LOG': str(guard_log),
        'HC_GUARD_DENY_PATHS': f"{DATA / 'hidden'}:{DATA / 'indic'}:{EVROOT / 'private'}",
        'HC_MODEL_REGISTRY': str(ROOT / 'models' / 'registry.json'),
        'http_proxy': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9',
        'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9', 'no_proxy': '127.0.0.1,localhost',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OMP_NUM_THREADS': env.get('OMP_NUM_THREADS', '2'),
    })
    return env

def predict(cand, task, input_rows):
    """Run cand/bin/predict on {id, field} rows only (gold labels never reach the candidate)."""
    field = FIELDS[task]
    if any(set(r) != {'id', field} for r in input_rows): raise ValueError(f'predict input must hold only id and {field}')
    ids = [r['id'] for r in input_rows]
    if len(ids) != len(set(ids)): raise ValueError('duplicate input ids')
    cand = Path(cand).resolve()
    with tempfile.TemporaryDirectory(prefix='kavach-bench-') as temp:
        inp, out, timing, guard = (Path(temp) / x for x in ('in.jsonl', 'out.jsonl', 'time.txt', 'guard.log'))
        inp.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in input_rows), encoding='utf-8')
        cmd = [str(cand / 'bin/predict'), '--task', 'sms' if task == 'indic' else task, '--in', str(inp), '--out', str(out)]
        start = time.monotonic()
        try:
            subprocess.run(['/usr/bin/time', '-f', '%M', '-o', str(timing), *cmd], cwd=cand, env=sandbox_env(guard), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT_S)
        except subprocess.CalledProcessError as exc:
            tail = exc.stderr.decode('utf-8', 'replace')[-2000:]
            raise RuntimeError(f'{task}: bin/predict exited {exc.returncode}; stderr tail:\n{tail}') from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'{task}: bin/predict exceeded {TIMEOUT_S}s') from None
        wall = time.monotonic() - start
        predictions = rows(out)
        mapped = {r['id']: r.get('label') for r in predictions}
        if set(mapped) != set(ids) or len(predictions) != len(ids): raise ValueError('prediction IDs do not equal input IDs')
        invalid = sum(not valid_label(v) for v in mapped.values())
        blocked = sum(1 for line in guard.read_text().splitlines() if line.strip()) if guard.exists() else 0
        return mapped, {'wall_s': round(wall, 3), 'peak_rss_mb': round(int(timing.read_text().strip()) / 1024, 1), 'invalid': invalid, 'guard_events': blocked}

def fixture_inputs(task, data):
    field = FIELDS[task]
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
