import copy
import pytest
from compare_v3 import compare, EXPECTED_HIDDEN


def run(score):
    return {'candidate_hash': 'a' * 64, 'session_id': 'test-session', 'rss_method': 'systemd_scope', 'isolation_method': 'bwrap', 'score': score, 'quick': False, 'failures': [], 'infra_errors': [], 'promotable': True,
            'scores': {'D': .8, 'I': .8, 'E': .8},
            'detection': {t: {'conservative': {'f1': .8, 'fpr': .02}} for t in ('sms','url','indic','flow')},
            'india': {'injection_recall': .8, 'benign_ai_mention_fpr': .02},
            'latency_s_per_item': 2, 'peak_process_tree_rss_gb': 2,
            'host_during': {'cpu_steal_percent_max': 0}, 'contended': False, 'host_start': {'load_average': [1, 1, 1], 'cpu_steal_percent': 0},
            'host_end': {'load_average': [1, 1, 1], 'cpu_steal_percent': 0},
            'hidden_sha256': dict(EXPECTED_HIDDEN)}


@pytest.fixture(autouse=True)
def best_pin(monkeypatch, tmp_path):
    import compare_v3
    pin = tmp_path / 'BEST.sha256'
    pin.write_text('a' * 64 + '\n')
    monkeypatch.setattr(compare_v3, 'BEST_PIN', pin)


def compare_pair(b, c):
    bs, cs = [copy.deepcopy(b), copy.deepcopy(b)], [copy.deepcopy(c), copy.deepcopy(c)]
    for i, r in enumerate(bs):
        r.update(stamp=f'20261121-10000{i*2}-000000', candidate='BEST')
    for i, r in enumerate(cs):
        r.update(stamp=f'20261121-10000{i*2+1}-000000', candidate='CAND')
    return compare(bs, cs, .5)


def test_promotion_and_score_threshold():
    b, c = run(70), run(71)
    assert compare_pair(b, c)['pass']
    c['score'] = 70.49
    assert not compare_pair(b, c)['pass']


@pytest.mark.parametrize('path,value', [
    (('scores','E'),.78), (('detection','sms','conservative','f1'),.78),
    (('detection','url','conservative','fpr'),.026),
    (('india','injection_recall'),.79), (('india','benign_ai_mention_fpr'),.03),
    (('latency_s_per_item',),2.21), (('peak_process_tree_rss_gb',),2.11),
])
def test_each_regression_gate(path, value):
    b, c = run(70), run(71)
    target = c
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    assert not compare_pair(b, c)['pass']


def test_rejects_noninterleaved_runs():
    b, c = run(70), run(71)
    bs = [dict(b, stamp=f'20261121-10000{i}-000000', candidate='BEST') for i in (0, 1)]
    cs = [dict(c, stamp=f'20261121-10000{i}-000000', candidate='CAND') for i in (2, 3)]
    with pytest.raises(ValueError, match='interleaved'):
        compare(bs, cs, .5)


def test_missing_and_failures_fail_closed():
    b, c = run(70), run(71)
    c['failures'] = ['timeout']
    assert not compare_pair(b,c)['pass']
    c['failures'] = []
    del c['latency_s_per_item']
    with pytest.raises(ValueError): compare_pair(b,c)
    with pytest.raises(ValueError): compare([b],[c],.5)


def test_relative_caps_and_sanity_caps_are_distinct():
    b, c = run(70), run(71)
    b['latency_s_per_item'], c['latency_s_per_item'] = 5, 5.5
    b['peak_process_tree_rss_gb'], c['peak_process_tree_rss_gb'] = 2.8, 2.93
    assert compare_pair(b, c)['pass']
    c['latency_s_per_item'] = 5.51
    assert not compare_pair(b, c)['pass']
    b['latency_s_per_item'], c['latency_s_per_item'] = 10, 10.01
    assert not compare_pair(b, c)['pass']
    c['latency_s_per_item'], c['peak_process_tree_rss_gb'] = 10, 3.01
    assert not compare_pair(b, c)['pass']


@pytest.mark.parametrize('change', ['contended', 'missing_flag', 'load', 'missing_host', 'missing_steal'])
def test_contended_or_unmeasured_comparison_fails(change):
    b, c = run(70), run(71)
    if change == 'contended': c['contended'] = True
    if change == 'missing_flag': del c['contended']
    if change == 'load': c['host_start']['load_average'][0] = 1.50001
    if change == 'missing_host': del c['host_end']
    if change == 'missing_steal': del c['host_start']['cpu_steal_percent']
    assert not compare_pair(b, c)['pass']


def test_each_candidate_run_meets_relative_caps():
    for metric, bad in [('latency_s_per_item', 2.21), ('peak_process_tree_rss_gb', 2.11)]:
        b, c = run(70), run(71)
        bs = [dict(b, stamp=f'20261121-10000{i*2}-000000', candidate='BEST') for i in range(2)]
        cs = [dict(c, stamp=f'20261121-10000{i*2+1}-000000', candidate='CAND') for i in range(2)]
        cs[0][metric] = bad
        cs[1][metric] = 1.0  # mean passes but one run does not
        assert not compare(bs, cs, .5)['pass']


@pytest.mark.parametrize('field,bad', [('candidate_hash', 'b' * 64), ('session_id', 'other'), ('rss_method', 'proc_fallback')])
def test_binding_rejects_changed_run(field, bad):
    b, c = run(70), run(71)
    bs = [dict(b, stamp=f'20261121-10000{i*2}-000000', candidate='BEST') for i in range(2)]
    cs = [dict(c, stamp=f'20261121-10000{i*2+1}-000000', candidate='CAND') for i in range(2)]
    cs[1][field] = bad
    with pytest.raises(ValueError):
        compare(bs, cs, .5)


def test_best_pin_and_fallback_fail_closed(best_pin):
    import compare_v3
    b, c = run(70), run(71)
    b['candidate_hash'] = 'b' * 64
    with pytest.raises(ValueError, match='BEST content hash'):
        compare_pair(b, c)
    b = run(70)
    b['rss_method'] = c['rss_method'] = 'proc_fallback'
    with pytest.raises(ValueError, match='systemd_scope'):
        compare_pair(b, c)
    b = run(70)
    c = run(71)
    c['host_during']['cpu_steal_percent_max'] = 21
    assert not compare_pair(b, c)['pass']


def test_promotion_updates_pin_and_rejects_best_drift(monkeypatch, tmp_path):
    import promote_v3
    from run_eval import candidate_hash
    best = tmp_path / 'BEST'
    cand = tmp_path / 'candidate'
    best.mkdir()
    cand.mkdir()
    (best / 'program').write_text('old')
    (cand / 'program').write_text('new')
    pin = tmp_path / 'BEST.sha256'
    pin.write_text(candidate_hash(best) + '\n')
    digest = candidate_hash(cand)
    monkeypatch.setattr(promote_v3, 'compare', lambda *_: {'pass': True})
    three = [{}, {}, {}]
    with pytest.raises(ValueError, match='exactly three runs'):
        promote_v3.promote(cand, best, [{}, {}], [{'candidate_hash': digest}] * 2, .5, pin)
    promote_v3.promote(cand, best, three, [{'candidate_hash': digest}] * 3, .5, pin)
    assert pin.read_text().strip() == candidate_hash(best) == digest
    (best / 'program').write_text('drift')
    with pytest.raises(ValueError, match='current BEST differs'):
        promote_v3.promote(cand, best, three, [{'candidate_hash': digest}] * 3, .5, pin)


@pytest.mark.parametrize('mutate', ['missing', 'differs', 'one_run'])
def test_hidden_hashes_must_match_controller_pin(mutate):
    b, c = run(70), run(71)
    if mutate == 'missing':
        del c['hidden_sha256']
    elif mutate == 'differs':
        c['hidden_sha256']['sms_test'] = 'f' * 64
    if mutate == 'one_run':
        bs, cs = [copy.deepcopy(b), copy.deepcopy(b)], [copy.deepcopy(c), copy.deepcopy(c)]
        cs[1]['hidden_sha256'] = dict(EXPECTED_HIDDEN, flow_test='e' * 64)
        for i, r in enumerate(bs):
            r.update(stamp=f'20261121-10000{i*2}-000000', candidate='BEST')
        for i, r in enumerate(cs):
            r.update(stamp=f'20261121-10000{i*2+1}-000000', candidate='CAND')
        with pytest.raises(ValueError, match='hidden data hashes'):
            compare(bs, cs, .5)
        return
    with pytest.raises(ValueError, match='hidden data hashes'):
        compare_pair(b, c)


def test_candidate_hash_ignores_python_caches(tmp_path):
    from run_eval import candidate_hash
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg' / 'mod.py').write_text('x = 1\n')
    before = candidate_hash(tmp_path)
    (tmp_path / 'pkg' / '__pycache__').mkdir()
    (tmp_path / 'pkg' / '__pycache__' / 'mod.cpython-312.pyc').write_bytes(b'cache')
    (tmp_path / '.pytest_cache').mkdir()
    (tmp_path / '.pytest_cache' / 'v').write_text('cache')
    (tmp_path / 'stray.pyc').write_bytes(b'cache')
    assert candidate_hash(tmp_path) == before
    (tmp_path / 'pkg' / 'mod.py').write_text('x = 2\n')
    assert candidate_hash(tmp_path) != before
