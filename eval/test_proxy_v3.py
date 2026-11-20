import pytest
from proxy_v3 import conservative, grounding, mean, measurements_ok, total, tree_rss_kb


def test_conservative_penalty_and_undefined():
    r = conservative({'a': 1, 'b': 0, 'c': 0}, {'a': 1, 'b': 1, 'c': 0}, .03)
    assert r['score'] == pytest.approx((2/3)*(1-.5))
    assert conservative({}, {}, .03)['score'] == 0
    assert conservative({'a': 0}, {'a': 'uncertain'}, .03)['conservative']['fpr'] == 1


def test_weighted_total_and_mean_of_totals():
    assert total(1, 1, 1, 1) == pytest.approx(100)
    assert mean([total(1, 0, 0, 0), total(0, 1, 1, 1)]) == pytest.approx(50)


@pytest.mark.parametrize('src,expl,expected', [
    ('Pay the fee now', 'The message asks for a payment.', True),
    ('Your payment was received', 'The message asks for a payment.', False),
    ('Please visit the branch tomorrow', 'It requests a payment.', False),
    ('Please call the branch', 'The notice contains a phone call request.', True),
    ('Your balance is available', 'The message requests an OTP.', False),
    ('A notice', 'Never share your OTP. Verify via the official app.', True),
    ('A notice', 'The notice does not ask for payment.', True),
    ('A notice', 'No risk found. Verify independently.', True),
    ('Download the app', 'It tells you to install an app.', True),
    ('Hello', 'The sender demands that you transfer money.', False),
    ('Hello', '', True),
])
def test_grounding(src, expl, expected):
    assert grounding(src, expl) is expected


def test_rss_uses_simultaneous_sum(tmp_path):
    for pid, rss in ((1, 20), (2, 30)):
        p = tmp_path / str(pid)
        p.mkdir()
        (p / 'status').write_text(f'VmRSS:\t{rss} kB\nVmHWM:\t999 kB\n')
    assert tree_rss_kb([1, 2], tmp_path) == 50
    assert tree_rss_kb([3], tmp_path) is None


@pytest.mark.parametrize('lat,rss,timed,expected', [(4.5,2.6,False,True),(4.50001,2.6,False,False),
    (4.5,2.60001,False,False),(None,1,False,False),(1,None,False,False),(1,1,True,False)])
def test_measurement_gate(lat,rss,timed,expected):
    assert measurements_ok(lat,rss,timed) is expected


def test_repeats_run_whole_evaluator_and_average_scores(monkeypatch, capsys):
    import json
    import sys
    import run_eval
    calls = []
    def fake(a, index):
        calls.append(index)
        return {'score': [20, 60][index], 'proxy_v2_legacy': 10,
                'scores': {'D': index, 'I': 0, 'E': index, 'P': 0, 'C': 1},
                'detection': {'sms': {'conservative': {'f1': index}}},
                'failures': [], 'infra_errors': [], 'promotable': True}
    monkeypatch.setattr(run_eval, 'run_once', fake)
    monkeypatch.setattr(sys, 'argv', ['eval', 'candidate', '--repeats', '2'])
    assert run_eval.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert calls == [0, 1]
    assert result['score'] == 40
    assert result['scores']['E'] == .5
    assert result['detection']['sms']['conservative']['f1'] == .5


def test_missing_india_is_infra_failure(monkeypatch, tmp_path):
    import argparse
    import run_eval
    cand = tmp_path / 'candidate'
    (cand / 'bin').mkdir(parents=True)
    (cand / 'bin/predict').touch()
    (cand / 'bin/explain').touch()
    (tmp_path / 'research/evals').mkdir(parents=True)
    monkeypatch.setattr(run_eval, 'PROJ', tmp_path)
    monkeypatch.setattr(run_eval, 'HIDDEN', tmp_path / 'absent')
    monkeypatch.setattr(run_eval, 'EVROOT', tmp_path / 'private')
    result = run_eval.run_once(argparse.Namespace(candidate=str(cand), label=None, quick=False, repeats=1), 0)
    assert not result['promotable']
    assert any('adaptive India v2 data missing or invalid' in e for e in result['infra_errors'])
