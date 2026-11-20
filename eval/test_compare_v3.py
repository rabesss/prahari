import copy
import pytest
from compare_v3 import compare


def run(score):
    return {'candidate_hash': 'a' * 64, 'session_id': 'test-session', 'rss_method': 'proc_fallback', 'score': score, 'quick': False, 'failures': [], 'infra_errors': [], 'promotable': True,
            'scores': {'D': .8, 'I': .8, 'E': .8},
            'detection': {t: {'conservative': {'f1': .8, 'fpr': .02}} for t in ('sms','url','indic','flow')},
            'india': {'injection_recall': .8, 'benign_ai_mention_fpr': .02},
            'latency_s_per_item': 2, 'peak_process_tree_rss_gb': 2,
            'contended': False, 'host_start': {'load_average': [1, 1, 1], 'cpu_steal_percent': 0},
            'host_end': {'load_average': [1, 1, 1], 'cpu_steal_percent': 0}}


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


@pytest.mark.parametrize('field,bad', [('candidate_hash', 'b' * 64), ('session_id', 'other'), ('rss_method', 'systemd_scope')])
def test_binding_rejects_changed_run(field, bad):
    b, c = run(70), run(71)
    bs = [dict(b, stamp=f'20261121-10000{i*2}-000000', candidate='BEST') for i in range(2)]
    cs = [dict(c, stamp=f'20261121-10000{i*2+1}-000000', candidate='CAND') for i in range(2)]
    cs[1][field] = bad
    with pytest.raises(ValueError):
        compare(bs, cs, .5)
