import pytest
from proxy_v3 import conservative, grounding, mean, measurements_ok, total, tree_rss_kb


def test_conservative_penalty_and_undefined():
    r = conservative({'a': 1, 'b': 0, 'c': 0}, {'a': 1, 'b': 1, 'c': 0}, .03)
    assert r['score'] == pytest.approx((2/3)*(1-.5))
    assert conservative({}, {}, .03)['score'] == 0
    assert conservative({}, {}, .03)['conservative']['fpr'] == 0
    assert conservative({'a': 0}, {'a': 'uncertain'}, .03)['conservative']['fpr'] == 1


def test_weighted_total_and_mean_of_totals():
    assert total(1, 1, 1, 1) == pytest.approx(100)
    assert mean([total(1, 0, 0, 0), total(0, 1, 1, 1)]) == pytest.approx(50)


@pytest.mark.parametrize('src,expl,expected', [
    ('Pay the fee now', 'The message asks for a payment.', True),
    ('Your payment was received', 'The message asks for a payment.', False),
    ('Your payment was received', 'The message says the payment was received.', True),
    ('Please visit the branch tomorrow', 'It requests a payment.', False),
    ('Please call the branch', 'The notice contains a phone call request.', True),
    ('Your balance is available', 'The message requests an OTP.', False),
    ('A notice', 'Never share your OTP. Verify via the official app.', True),
    ('A notice', 'The notice does not ask for payment.', True),
    ('A notice', 'No risk found. Verify independently.', True),
    ('Download the app', 'It tells you to install an app.', True),
    ('Go to https://example.org', 'The message contains a link.', True),
    ('Hello', 'The sender demands that you transfer money.', False),
    ('Hello', '', False),
    ('Hello', 'Too short to pass', False),
    ('No payment mentioned', 'Payment is what the message asks for.', True),
    ('Hello there', 'Payment is what the message asks for.', False),
    ('Hello there', 'The sender requested a payment.', False),
    ('Hello there', 'The message wants a payment.', False),
    ('सिर्फ एक साधारण संदेश', 'संदेश भुगतान मांगता है।', False),
    ('भुगतान मांगता है', 'यह संदेश अभी भुगतान मांगता है।', True),
    ('एक साधारण संदेश', 'यह संदेश अभी भुगतान मांगता है।', False),
    ('Meet at 5 p.m. today', 'The message contains a link.', False),
    ('Meet at 5 i.e. later', 'The message contains a link.', False),
    ('Ordinary text here', "If it asks for your OTP, don't share it.", True),
    ('Ordinary text here', "The message asks for payment, so don't pay.", False),
    ('Ordinary text here', 'The message asks for payment if you agree.', False),
    ('Hello there', 'If you are worried, the sender asks for payment.', False),
    ('Hello there', 'The message contains a greeting, so do not share your OTP.', True),
    ('Hello there', 'When the message asks for your OTP, do not share it.', True),
    ('साधारण संदेश', 'यह संदेश भुगतान नहीं मांगता है।', True),
    ('Receipt for your payment', 'The sender requested a payment.', False),
    ('Receipt for the fee paid', 'The sender requested a payment.', False),
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
    from run_eval import tree_pids
    for pid, children in ((1, '2'), (2, '')):
        task = tmp_path / str(pid) / 'task' / str(pid)
        task.mkdir(parents=True)
        (task / 'children').write_text(children)
    assert tree_pids(1, tmp_path) == {1, 2}
    assert tree_rss_kb(tree_pids(1, tmp_path), tmp_path) == 50


@pytest.mark.parametrize('lat,rss,timed,expected', [(10,3,False,True),(10.00001,3,False,False),
    (10,3.00001,False,False),(None,1,False,False),(1,None,False,False),(1,1,True,False)])
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
    assert set(result['host_start']) == {'load_average', 'cpu_steal_percent'}
    assert set(result['host_end']) == {'load_average', 'cpu_steal_percent'}
    assert result['contended'] == (result['host_start']['load_average'][0] > 1.5)
    assert not result['promotable']
    assert any('adaptive India v2 data missing or invalid' in e for e in result['infra_errors'])


def test_missing_host_sample_is_infra_failure(monkeypatch, tmp_path):
    import argparse
    import run_eval
    (tmp_path / 'research/evals').mkdir(parents=True)
    monkeypatch.setattr(run_eval, 'PROJ', tmp_path)
    monkeypatch.setattr(run_eval, 'EVROOT', tmp_path / 'private')
    monkeypatch.setattr(run_eval, 'host_snapshot', lambda: None)
    result = run_eval.run_once(argparse.Namespace(candidate=str(tmp_path / 'missing'), label=None, quick=False), 0)
    assert result['contended'] is None
    assert not result['promotable']
    assert 'host load or CPU steal measurement unavailable' in result['infra_errors']


def test_process_timeout_and_measurement(tmp_path):
    import os
    import sys
    from run_eval import run_proc
    result = run_proc([sys.executable, '-c', 'import time; time.sleep(2)'],
                      os.environ.copy(), .15, tmp_path, tmp_path / 'proc.log')
    assert result['timed_out']
    assert result['rc'] != 0
    # A timeout may precede scope creation, leaving no RSS measurement.
    assert not measurements_ok(1, result['peak_rss_mb'], result['timed_out'])


def test_corrupt_india_is_infra_failure(monkeypatch, tmp_path):
    import argparse
    import run_eval
    cand = tmp_path / 'candidate'
    (cand / 'bin').mkdir(parents=True)
    (cand / 'bin/predict').touch()
    (cand / 'bin/explain').touch()
    (tmp_path / 'research/evals').mkdir(parents=True)
    hidden = tmp_path / 'hidden'
    hidden.mkdir()
    (hidden / 'india_hidden_v2.jsonl').write_text('{}\n')
    monkeypatch.setattr(run_eval, 'PROJ', tmp_path)
    monkeypatch.setattr(run_eval, 'HIDDEN', hidden)
    monkeypatch.setattr(run_eval, 'EVROOT', tmp_path / 'private')
    result = run_eval.run_once(argparse.Namespace(candidate=str(cand), label=None, quick=False, repeats=1), 0)
    assert not result['promotable']
    assert any('SHA-256 mismatch' in e for e in result['infra_errors'])


def test_run_scratch_is_fresh_and_removed(monkeypatch, tmp_path):
    import argparse
    import run_eval
    candidate = tmp_path / 'original'
    candidate.mkdir()
    (candidate / 'source').write_text('unchanged')
    monkeypatch.setattr(run_eval, 'EVROOT', tmp_path / 'eval')
    monkeypatch.setattr(run_eval, 'LOCK', tmp_path / 'eval/lock')
    seen = []
    def fake(a, index, original, scratch, digest, queued, full_start):
        assert original == candidate
        assert (scratch / 'candidate/source').read_text() == 'unchanged'
        assert digest == run_eval.candidate_hash(candidate)
        (scratch / 'candidate/source').write_text('local cache')
        seen.append(scratch)
        return {}
    monkeypatch.setattr(run_eval, '_run_once', fake)
    args = argparse.Namespace(candidate=str(candidate))
    run_eval.run_once(args, 0)
    run_eval.run_once(args, 1)
    assert seen[0] != seen[1] and all(not p.exists() for p in seen)
    assert (candidate / 'source').read_text() == 'unchanged'


def test_fallback_kills_background_session(tmp_path):
    import os
    import sys
    from run_eval import run_proc
    command = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); print("done")'
    result = run_proc([sys.executable, '-c', command], os.environ.copy(), 5, tmp_path,
                      tmp_path / 'proc.log', rss_method='proc_fallback')
    assert result['rc'] == 0 and not result['stray_process']
    assert result['rss_method'] == 'proc_fallback' and result['peak_rss_mb'] > 0


def test_isolation_environment(tmp_path):
    from run_eval import isolation_env
    env = isolation_env(tmp_path)
    assert set(env) == {'HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'TMPDIR'}
    assert len(set(env.values())) == 4
    assert all(__import__('pathlib').Path(p).is_dir() and __import__('pathlib').Path(p).parent == tmp_path for p in env.values())


def test_original_change_and_contention_prevent_promotion(monkeypatch, tmp_path):
    import argparse
    import run_eval
    candidate = tmp_path / 'candidate'
    (candidate / 'bin').mkdir(parents=True)
    (candidate / 'bin/predict').touch()
    (candidate / 'bin/explain').touch()
    (tmp_path / 'research/evals').mkdir(parents=True)
    monkeypatch.setattr(run_eval, 'PROJ', tmp_path)
    monkeypatch.setattr(run_eval, 'HIDDEN', tmp_path / 'absent')
    monkeypatch.setattr(run_eval, 'EVROOT', tmp_path / 'eval')
    monkeypatch.setattr(run_eval, 'LOCK', tmp_path / 'eval/lock')
    def sample():
        (candidate / 'changed').write_text('changed')
        return {'load_average': [2, 1, 1], 'cpu_steal_percent': 0}
    monkeypatch.setattr(run_eval, 'host_snapshot', sample)
    result = run_eval.run_once(argparse.Namespace(candidate=str(candidate), label=None, quick=False), 0)
    assert 'candidate modified during eval' in result['failures']
    assert result['contended'] and not result['promotable']
    assert result['host_during']['load_1m_max'] == 2


def test_fallback_accounts_for_child_high_water(monkeypatch, tmp_path):
    import os
    import sys
    import run_eval
    class Usage:
        ru_maxrss = 100000
    monkeypatch.setattr(run_eval.resource, 'getrusage', lambda _: Usage())
    result = run_eval.run_proc([sys.executable, '-c', 'import time; time.sleep(.2)'],
                               os.environ.copy(), 5, tmp_path, tmp_path / 'proc.log', rss_method='proc_fallback')
    assert result['peak_rss_mb'] >= 100000 / 1024


def test_user_scope_measures_and_reaps_descendants(tmp_path):
    import os
    import sys
    import run_eval
    env = os.environ.copy()
    if not run_eval.scope_available(env):
        pytest.skip('user scopes unavailable')
    code = ('import os,time; p=os.fork(); '
            'os._exit(0) if p else (os.setsid(), time.sleep(30))')
    result = run_eval.run_proc([sys.executable, '-c', code], env, 5, tmp_path,
                               tmp_path / 'proc.log', rss_method='systemd_scope')
    assert result['rss_method'] == 'systemd_scope'
    assert result['rc'] == 0 and result['peak_rss_mb'] > 0 and not result['stray_process']


def test_frozen_explanation_score_does_not_depend_on_consistency_v2(monkeypatch):
    import run_eval
    item = {'input': 'some input', 'label': 1}
    output = {'explanation': 'These are five ordinary words here.'}
    checks = {'consistency': 1.0}
    monkeypatch.setattr(run_eval, 'explain_checks', lambda *_: (.83, checks, True))
    monkeypatch.setattr(run_eval, 'grounding', lambda *_: True)
    monkeypatch.setattr(run_eval, 'consistent_v2', lambda *_: False)
    score, reported_checks, valid, grounded, diagnostic = run_eval.explanation_components(item, output)
    assert score == .83 and reported_checks['consistency'] == 1.0 and valid
    assert grounded == 1 and diagnostic == 0
    assert .85 * score + .15 * grounded == pytest.approx(.8555)


def test_cleanup_census_waits_for_exiting_members():
    from run_eval import survivors_after_kill
    states = iter([{123}, set()])
    assert not survivors_after_kill(lambda: next(states), timeout=1)
    assert survivors_after_kill(lambda: {123}, timeout=0) == {123}


def test_fake_completion_cannot_override_process_exit(tmp_path):
    import os
    import sys
    import run_eval
    env = os.environ.copy()
    if not run_eval.scope_available(env):
        pytest.skip('user scopes unavailable')
    fake = tmp_path / 'fake.status'
    env['PRAHARI_STAGE_STATUS'] = str(fake)
    code = f"import pathlib; pathlib.Path({str(fake)!r}).write_text('0'); raise SystemExit(7)"
    result = run_eval.run_proc([sys.executable, '-c', code], env, 5, tmp_path, tmp_path / 'proc.log', rss_method='systemd_scope')
    assert result['rc'] == 7


def test_candidate_hash_is_independent_of_checkout_umask(tmp_path):
    import shutil
    from run_eval import candidate_hash
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(mode=0o755)
    (a / 'run').write_text('same')
    (a / 'run').chmod(0o755)
    shutil.copytree(a, b)
    b.chmod(0o775)
    (b / 'run').chmod(0o775)
    assert candidate_hash(a) == candidate_hash(b)
    (b / 'run').chmod(0o664)
    assert candidate_hash(a) != candidate_hash(b)


@pytest.mark.parametrize('expl', [
    'The message has a payment link and an OTP.',
    'A payment link was included by the sender.',
    'Payment is contained in this message.',
    'The text mentioned an OTP code.',
    'You are told to transfer money now.',
    'यह संदेश में भुगतान चाहती है।',
])
def test_verb_independent_ungrounded_claims(expl):
    assert not grounding('Hello', expl)


@pytest.mark.parametrize('expl', [
    'You may want to call 1930 to report fraud.',
    'In this situation you should call the police.',
    'Report it at https://sancharsaathi.gov.in.',
    'The message does not contain a link or ask for a payment.',
])
def test_advice_and_negated_claims(expl):
    assert grounding('Hello', expl)


def test_link_and_payment_grounding_boundaries():
    assert not grounding('see report.pdf', 'The message contains a link.')
    assert not grounding('node.js', 'The message contains a link.')
    assert not grounding('email user@example.com', 'The message contains a link.')
    assert grounding('Pay the fee at example.com', 'The message asks for payment at example.com.')
    assert grounding('Pay the fee', 'The message asks for payment at https://example.com.')
    assert not grounding('Receipt of your payment', 'Deposit the receipt amount right now.')
    assert not grounding('Hello', 'Never share an OTP. The sender demands payment now.')


def test_stage_environment_is_an_allowlist():
    from run_eval import stage_environment
    result = stage_environment({'PATH': '/bad', 'HOME': '/scratch', 'HF_HOME': '/shared',
                                'XDG_CONFIG_HOME': '/shared', 'XDG_RUNTIME_DIR': '/run/user/1',
                                'DBUS_SESSION_BUS_ADDRESS': 'address', 'HC_PY': '/python'})
    assert result == {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/scratch', 'HC_PY': '/python'}


def test_bwrap_keeps_cgroups_read_only():
    import shutil
    import subprocess
    if not shutil.which('bwrap'):
        pytest.skip('bwrap unavailable')
    basic = subprocess.run(['bwrap', '--ro-bind', '/', '/', '--', '/bin/true'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if basic.returncode != 0:
        pytest.skip('bwrap cannot run')
    probe = subprocess.run(['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--tmpfs', '/tmp', '--tmpfs', '/dev/shm',
                            '--', '/usr/bin/python3', '-c',
                            'import os; assert os.statvfs("/sys/fs/cgroup").f_flag & os.ST_RDONLY; assert os.urandom(1); open("/dev/null", "w").write("x")'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert probe.returncode == 0
