"""Compare same-session full run summaries using the round-3 promotion gates."""
import argparse
import datetime as dt
import json
import math
import re
from statistics import mean
from pathlib import Path

BEST_PIN = Path(__file__).resolve().parents[1] / 'research/evals/BEST.sha256'

TASKS = ('sms', 'url', 'indic', 'flow')

# Controller-owned digests of the hidden gold every comparable run must have scored against.
EXPECTED_HIDDEN = {
    'sms_test': '0a1a0060e86eccb79a05c43072d8c7fec3d491c509ec39998bf3b6d7f55c1fa4',
    'url_test': '6b7bd10ed277f7e150fe790b771410b5b3756d79926a92649bd17faa44730798',
    'indic_test': 'bd8fe7d31bec627923dbe998730574bd1e77e76f2527c8b0b2f2990f7738f524',
    'flow_test': '277f7a8388cc72bd7df39794101f6d7dffdfad7634bb2d0effab5b7d617b5b43',
    'explain_set': '8603235cc842b076b4437d0a1f2e936c01cefe232693af5f4d04f754083dd888',
    'india_hidden_v2': '532e017843381b23879a92b7559f88bb8cf23dd650df98c00f68ae0224995fb0',
}


def value(run, *path):
    try:
        v = run
        for key in path:
            v = v[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError
        return v
    except (KeyError, TypeError, ValueError):
        raise ValueError('missing or invalid metric: ' + '.'.join(path))


def compare(best, candidate, threshold):
    if len(best) != len(candidate) or len(best) not in (2, 3):
        raise ValueError('need two or three runs per candidate')
    if not math.isfinite(threshold) or threshold < .5:
        raise ValueError('threshold must be finite and at least 0.5')
    try:
        ordered = sorted([(dt.datetime.strptime(r['stamp'], '%Y%m%d-%H%M%S-%f'), side)
                          for side, runs in ((0, best), (1, candidate)) for r in runs])
        if len({t for t, _ in ordered}) != len(ordered) or any(a[1] == b[1] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('runs must be interleaved')
        for runs in (best, candidate):
            if not all(isinstance(r.get('candidate'), str) and r['candidate'] == runs[0]['candidate'] for r in runs):
                raise ValueError('candidate path changed within a group')
        for runs in (best, candidate):
            if not all(isinstance(r.get('candidate_hash'), str) and re.fullmatch(r'[0-9a-f]{64}', r['candidate_hash'])
                       and r['candidate_hash'] == runs[0]['candidate_hash'] for r in runs):
                raise ValueError('candidate content hash missing or changed within group')
        if not all(isinstance(r.get('session_id'), str) and r['session_id'].strip()
                   and r['session_id'] == best[0]['session_id'] for r in best + candidate):
            raise ValueError('comparison session id missing or changed')
        if not all(r.get('rss_method') == 'systemd_scope' and r.get('isolation_method') == 'bwrap' for r in best + candidate):
            raise ValueError('promotion requires systemd_scope and bwrap')
        try:
            pinned = BEST_PIN.read_text().strip()
        except OSError:
            raise ValueError('BEST pin missing')
        if not re.fullmatch(r'[0-9a-f]{64}', pinned) or best[0]['candidate_hash'] != pinned:
            raise ValueError('BEST content hash does not match pin')
        if not all(r.get('hidden_sha256') == EXPECTED_HIDDEN for r in best + candidate):
            raise ValueError('hidden data hashes missing or differ from the controller pin')
        if best[0]['candidate'] == candidate[0]['candidate']:
            raise ValueError('BEST and candidate paths must differ')
    except (KeyError, TypeError):
        raise ValueError('missing run stamp or candidate')
    for r in best + candidate:
        if r.get('quick') is not False or r.get('failures') != [] or r.get('infra_errors') != [] or r.get('promotable') is not True:
            return {'pass': False, 'failures': ['a full run failed or is not promotable']}
        if r.get('contended') is not False:
            return {'pass': False, 'failures': ['contended or unmeasured run; rerun the comparison']}
        for end in ('host_start', 'host_end'):
            snapshot = r.get(end)
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get('load_average'), list) or len(snapshot['load_average']) != 3:
                return {'pass': False, 'failures': ['missing host measurement; rerun the comparison']}
            try:
                vals = [value(snapshot, 'cpu_steal_percent')] + [value({'load': v}, 'load') for v in snapshot['load_average']]
            except ValueError:
                return {'pass': False, 'failures': ['invalid host measurement; rerun the comparison']}
            if not 0 <= vals[0] <= 100 or any(v < 0 for v in vals[1:]) or (end == 'host_start' and vals[1] > 1.5):
                return {'pass': False, 'failures': ['contended or invalid host measurement; rerun the comparison']}
        try:
            steal = value(r, 'host_during', 'cpu_steal_percent_max')
        except ValueError:
            return {'pass': False, 'failures': ['missing CPU steal measurement']}
        if not 0 <= steal <= 20:
            return {'pass': False, 'failures': ['CPU steal exceeded threshold']}
        if not (0 < value(r, 'latency_s_per_item') <= 10.0 and 0 < value(r, 'peak_process_tree_rss_gb') <= 3.0):
            return {'pass': False, 'failures': ['performance sanity cap failed']}
    def avg(runs, *path):
        return mean(value(r, *path) for r in runs)
    reasons = []
    delta = avg(candidate, 'score') - avg(best, 'score')
    if delta < threshold:
        reasons.append('score improvement below threshold')
    for component in ('D', 'I', 'E'):
        if avg(candidate, 'scores', component) < avg(best, 'scores', component) - .01:
            reasons.append(component + ' fell by more than 1 percentage point')
    for task in TASKS:
        root = ('detection', task, 'conservative')
        if avg(candidate, *root, 'f1') < avg(best, *root, 'f1') - .01:
            reasons.append(task + ' F1 fell by more than 1 percentage point')
        if avg(candidate, *root, 'fpr') > avg(best, *root, 'fpr') + .005:
            reasons.append(task + ' FPR rose by more than 0.5 percentage point')
    if avg(candidate, 'india', 'injection_recall') < avg(best, 'india', 'injection_recall'):
        reasons.append('injection recall fell')
    if avg(candidate, 'india', 'benign_ai_mention_fpr') > avg(best, 'india', 'benign_ai_mention_fpr'):
        reasons.append('benign AI mention FPR rose')
    for metric, factor in (('latency_s_per_item', 1.10), ('peak_process_tree_rss_gb', 1.05)):
        b = avg(best, metric)
        if b <= 0 or any(value(r, metric) <= 0 or value(r, metric) > b * factor for r in candidate):
            reasons.append(metric + ' failed')
    return {'pass': not reasons, 'failures': reasons, 'delta': delta, 'threshold': threshold}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--best', nargs='+', required=True, type=Path)
    parser.add_argument('--candidate', nargs='+', required=True, type=Path)
    parser.add_argument('--threshold', required=True, type=float)
    args = parser.parse_args()
    try:
        result = compare([json.loads(p.read_text()) for p in args.best],
                         [json.loads(p.read_text()) for p in args.candidate], args.threshold)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        result = {'pass': False, 'failures': [str(exc)]}
    print(json.dumps(result))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
