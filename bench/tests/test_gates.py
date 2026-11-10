import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gate
import readiness
import stress
from common import digest


def test_uncertain_benign_is_not_correct():
    r=stress.evaluate([{'id':'x','label':0}], {'x':'uncertain'})
    assert not r['x']['correct']


def test_per_row_fixture_regression_fails(tmp_path, monkeypatch):
    f=tmp_path/'sms.jsonl'; f.write_text(json.dumps({'id':'x','input':'example','expect':0,'rationale':'benign'})+'\n')
    ref=tmp_path/'reference.json'; ref.write_text(json.dumps({'fixtures':{'sms.jsonl':{'sha256':digest(f),'n':1,'rows':{'x':{'expect':0,'prediction':0,'gate':True}}}}}))
    monkeypatch.setattr(gate,'FIXTURES',[f]); monkeypatch.setattr(gate,'predict',lambda *args: ({'x':1},{'invalid':0,'wall_s':0,'peak_rss_mb':1}))
    monkeypatch.setattr(sys,'argv',['gate.py','--reference',str(ref)])
    assert gate.main() == 1


def test_changed_fixture_requires_reference(tmp_path,monkeypatch,capsys):
    f=tmp_path/'sms.jsonl'; f.write_text(json.dumps({'id':'x','input':'example','expect':0,'rationale':'benign'})+'\n')
    ref=tmp_path/'reference.json'; ref.write_text(json.dumps({'fixtures':{'sms.jsonl':{'sha256':'wrong','n':1,'rows':{'x':{'expect':0,'prediction':0,'gate':True}}}}}))
    monkeypatch.setattr(gate,'FIXTURES',[f]); monkeypatch.setattr(gate,'predict',lambda *args: ({'x':0},{'invalid':0,'wall_s':0,'peak_rss_mb':1}))
    monkeypatch.setattr(sys,'argv',['gate.py','--reference',str(ref)])
    assert gate.main() == 1
    assert 'regenerate reference' in capsys.readouterr().out


def test_readiness_detects_sources_open_and_certainty(tmp_path):
    (tmp_path/'README.md').write_text('Setup offline compiled application demo')
    (tmp_path/'REPORT.md').write_text('\n'.join('## '+s for s in readiness.SECTIONS)+'\nhardware model performance demo video offline')
    (tmp_path/'DATA.md').write_text('UCI SMS Mendeley PhiUSIIL NSL-KDD Indian-context synthetic Llama karanverma19')
    (tmp_path/'app').mkdir(); (tmp_path/'app/server.py').write_text('import webbrowser\nwebbrowser.open(url)\nPAGE="This is definitely safe"\n')
    issues=readiness.check(tmp_path)
    assert any('bolewara' in x for x in issues)
    assert any('link opening' in x for x in issues)
    assert any('certainty phrase' in x for x in issues)


# Round-1 review regressions: predict sandbox and contract (DeepSeek V4.1 Flash, Grok 4.7), reference ratchet (Grok 4.7).
import os
import subprocess
import pytest
import common
import ratchet

FAKE = '''#!/usr/bin/env python3
import json, os, sys
a = sys.argv; inp = a[a.index('--in') + 1]; out = a[a.index('--out') + 1]
rows = [json.loads(x) for x in open(inp)]
mode = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
assert os.getcwd() == os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
assert not any(k.startswith(('GITHUB', 'GH_', 'OPENAI')) for k in os.environ)
if mode == 'fail': sys.stderr.write('boom-detail'); sys.exit(3)
ids = [r['id'] for r in rows]
if mode == 'dup': ids = ids + ids[:1]
if mode == 'missing': ids = ids[1:]
if mode == 'extra': ids = ids + ['zzz']
with open(out, 'w') as f:
    for i in ids: f.write(json.dumps({'id': i, 'label': 0}) + '\\n')
'''


def fake(tmp_path, mode):
    c = tmp_path / mode; (c / 'bin').mkdir(parents=True); p = c / 'bin/predict'; p.write_text(FAKE); p.chmod(0o755)
    return c


def test_predict_ok_and_sandboxed(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'x'); monkeypatch.setenv('OPENAI_API_KEY', 'x')
    pred, stats = common.predict(fake(tmp_path, 'ok'), 'sms', [{'id': 'a', 'text': 'hi'}, {'id': 'b', 'text': 'yo'}])
    assert pred == {'a': 0, 'b': 0} and stats['invalid'] == 0


@pytest.mark.parametrize('mode', ['dup', 'missing', 'extra'])
def test_predict_id_mismatch(tmp_path, mode):
    with pytest.raises(ValueError):
        common.predict(fake(tmp_path, mode), 'sms', [{'id': 'a', 'text': 'hi'}, {'id': 'b', 'text': 'yo'}])


def test_predict_surfaces_stderr(tmp_path):
    with pytest.raises(RuntimeError, match='boom-detail'):
        common.predict(fake(tmp_path, 'fail'), 'sms', [{'id': 'a', 'text': 'hi'}])


def test_predict_rejects_gold_label(tmp_path):
    with pytest.raises(ValueError, match='only id'):
        common.predict(fake(tmp_path, 'ok'), 'sms', [{'id': 'a', 'text': 'hi', 'label': 1}])


def test_dedupe_counts(tmp_path):
    f = tmp_path / 'd.jsonl'
    f.write_text(''.join(json.dumps(r) + '\n' for r in [{'id': 'a', 'label': 0}, {'id': 'a', 'label': 0}, {'id': 'b', 'label': 0}, {'id': 'b', 'label': 1}, {'id': 'c', 'label': 1}]))
    stats = {}; kept = common.rows(f, dedupe=stats)
    assert [r['id'] for r in kept] == ['a', 'c']
    assert stats == {'duplicates_dropped': 1, 'conflicting_ids_dropped': 1, 'conflicting_rows_dropped': 2}


def _git(repo, *args):
    subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)


def _ref(gate_x):
    return json.dumps({'fixtures': {'sms.jsonl': {'rows': {'x': {'gate': gate_x}, 'y': {'gate': False}}}}, 'stress': {}})


def _ratchet(repo, monkeypatch, base):
    monkeypatch.setattr(sys, 'argv', ['ratchet.py', base, '--root', str(repo)])
    return ratchet.main()


def test_ratchet(tmp_path, monkeypatch):
    repo = tmp_path; (repo / 'bench').mkdir()
    _git(repo, 'init', '-q'); _git(repo, 'config', 'user.email', 't@example.invalid'); _git(repo, 'config', 'user.name', 'T')
    (repo / 'bench/reference.json').write_text(_ref(True)); _git(repo, 'add', '.'); _git(repo, 'commit', '-qm', 'ref')
    base = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert _ratchet(repo, monkeypatch, base) == 0
    (repo / 'bench/reference.json').write_text(_ref(False))
    assert _ratchet(repo, monkeypatch, base) == 1
    (repo / 'bench/accepted_downgrades.json').write_text(json.dumps({'downgrades': [{'suite': 'fixtures', 'file': 'sms.jsonl', 'row': 'x', 'reason': 'fixture rewritten'}]}))
    assert _ratchet(repo, monkeypatch, base) == 0
    _git(repo, 'add', '.'); _git(repo, 'commit', '-qm', 'accept')
    (repo / 'bench/reference.json').write_text(_ref(True)); _git(repo, 'commit', '-qam', 'regate')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()
    (repo / 'bench/reference.json').write_text(_ref(False))
    assert _ratchet(repo, monkeypatch, head) == 1  # an entry already present at base does not cover a new downgrade


# Round-2 review regressions: ratchet relabel (DeepSeek V4.1 Flash), timeout kills the tree (CodeRabbit, DeepSeek),
# per-task predict failure keeps the report (CodeRabbit).
def test_ratchet_relabel_is_a_downgrade(tmp_path, monkeypatch):
    repo = tmp_path; (repo / 'bench').mkdir()
    _git(repo, 'init', '-q'); _git(repo, 'config', 'user.email', 't@example.invalid'); _git(repo, 'config', 'user.name', 'T')
    ref = lambda e: json.dumps({'fixtures': {'sms.jsonl': {'rows': {'x': {'expect': e, 'prediction': e, 'gate': True}}}},
                                'stress': {'s.jsonl': {'rows': {'h1': {'label': 1, 'prediction': 1, 'correct': True, 'gate': True}}}}})
    (repo / 'bench/reference.json').write_text(ref(1)); _git(repo, 'add', '.'); _git(repo, 'commit', '-qm', 'ref')
    base = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()
    (repo / 'bench/reference.json').write_text(ref(0))
    assert _ratchet(repo, monkeypatch, base) == 1


SLOW = '''#!/usr/bin/env python3
import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
open(os.environ['PIDFILE'], 'w').write(str(child.pid))
time.sleep(60)
'''


def test_predict_timeout_kills_tree(tmp_path, monkeypatch):
    c = tmp_path / 'slow'; (c / 'bin').mkdir(parents=True); p = c / 'bin/predict'; p.write_text(SLOW); p.chmod(0o755)
    pidfile = tmp_path / 'pid'; monkeypatch.setenv('PIDFILE', str(pidfile)); monkeypatch.setattr(common, 'TIMEOUT_S', 3)
    with pytest.raises(RuntimeError, match='exceeded'):
        common.predict(c, 'sms', [{'id': 'a', 'text': 'hi'}])
    pid = int(pidfile.read_text())
    import time as _t; _t.sleep(0.5)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_predict_env_strips_cloud_credentials(monkeypatch, tmp_path):
    for k in ('AWS_SECRET_ACCESS_KEY', 'HF_TOKEN', 'GOOGLE_APPLICATION_CREDENTIALS', 'AZURE_CLIENT_SECRET', 'HUGGING_FACE_HUB_TOKEN'):
        monkeypatch.setenv(k, 'x')
    env = common.sandbox_env(tmp_path / 'g.log')
    assert not {'AWS_SECRET_ACCESS_KEY', 'HF_TOKEN', 'GOOGLE_APPLICATION_CREDENTIALS', 'AZURE_CLIENT_SECRET', 'HUGGING_FACE_HUB_TOKEN'} & set(env)
    assert env['HF_HUB_OFFLINE'] == '1'


def test_run_records_predict_failure_and_writes_report(tmp_path, monkeypatch):
    import run
    dev = tmp_path / 'dev'; dev.mkdir()
    (dev / 'sms.jsonl').write_text(json.dumps({'id': 'a', 'text': 'hi', 'label': 0}) + '\n')
    prefix = tmp_path / 'out' / 'r'
    monkeypatch.setattr(sys, 'argv', ['run.py', '--cand', str(fake(tmp_path, 'fail')), '--data', str(dev), '--output-prefix', str(prefix)])
    assert run.main() == 1
    report = json.loads(prefix.with_suffix('.json').read_text())
    assert 'RuntimeError' in report['errors']['sms']


def test_ratchet_dropping_stress_correct_is_a_downgrade(tmp_path, monkeypatch):
    repo = tmp_path; (repo / 'bench').mkdir()
    _git(repo, 'init', '-q'); _git(repo, 'config', 'user.email', 't@example.invalid'); _git(repo, 'config', 'user.name', 'T')
    ref = lambda row: json.dumps({'fixtures': {}, 'stress': {'s.jsonl': {'rows': {'h1': row}}}})
    (repo / 'bench/reference.json').write_text(ref({'label': 1, 'prediction': 1, 'correct': True, 'gate': True}))
    _git(repo, 'add', '.'); _git(repo, 'commit', '-qm', 'ref')
    base = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True).stdout.strip()
    (repo / 'bench/reference.json').write_text(ref({'label': 1, 'prediction': 0, 'gate': True}))
    assert _ratchet(repo, monkeypatch, base) == 1  # (Grok 4.7) gate kept, correct dropped
