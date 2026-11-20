import subprocess
import sys
from pathlib import Path
import pytest

AUDIT = Path(__file__).resolve().parents[1] / 'audit_push.py'

def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

def setup_repo(path):
    git(path, 'init', '-q')
    git(path, 'config', 'user.email', 'test@example.invalid')
    git(path, 'config', 'user.name', 'Test')
    (path / 'README.md').write_text('start\n')
    git(path, 'add', '.')
    git(path, 'commit', '-qm', 'base')
    return git(path, 'rev-parse', 'HEAD')

def add(repo, path, data):
    p = repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'change')

def audit(repo, base, head='HEAD'):
    return subprocess.run([sys.executable, str(AUDIT), base, head], cwd=repo, text=True, capture_output=True)

def test_clean(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'clean.py', b'print(1)\n')
    result = audit(tmp_path, base)
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.parametrize(('path', 'content', 'rule'), [
    ('code.py', b'password=' + b'ultra-private-value\n', 'secret pattern'),
    ('data/raw.csv', b'data\n', 'path not uniquely allowlisted'),
    ('huge.py', b'x' * 1_000_001, 'size limit'),
    ('research/evals/20261110-run/details.json', b'{"id":"sms-abcdef123"}', 'leaf/array/id'),
    ('research/evals/20261110-run/run.log', b'user input and other content\n', 'non-status log line'),
])
def test_bad_content_fails_without_disclosure(tmp_path, path, content, rule):
    base = setup_repo(tmp_path); add(tmp_path, path, content)
    result = audit(tmp_path, base)
    assert result.returncode != 0
    assert rule in result.stdout
    assert 'ultra-private-value' not in result.stdout + result.stderr

def test_non_ancestor_fails(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'a.py', b'print(1)\n'); other = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'checkout', '-q', '--detach', base); add(tmp_path, 'b.py', b'print(2)\n')
    assert audit(tmp_path, other).returncode != 0

def test_intermediate_blob_is_checked(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'data.csv', b'private\n')
    git(tmp_path, 'rm', '-q', 'data.csv'); git(tmp_path, 'commit', '-qm', 'remove')
    assert audit(tmp_path, base).returncode != 0

SELFTEST_OK = b'[{"verdict": "malicious", "score": 1.0, "evidence": ["the domain ends in .top"]}, {"verdict": "benign", "score": 0.27, "evidence": []}]\n'

def test_selftest_app_log_allowed(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'research/evals/r1/app.log', SELFTEST_OK)
    assert audit(tmp_path, base).returncode == 0

@pytest.mark.parametrize('path,content', [
    ('research/evals/r1/app.log', b'[{"verdict": "malicious", "score": 1.0, "text": "raw message"}]\n'),
    ('research/evals/r1/app.log', b'[{"verdict": "malicious", "score": 1.0, "evidence": ["sms-0123abcd"]}]\n'),
    ('research/evals/r1/run.log', SELFTEST_OK),
])
def test_selftest_shape_only_in_app_log(tmp_path, path, content):
    base = setup_repo(tmp_path); add(tmp_path, path, content)
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'non-status log line' in r.stdout

def test_bench_result_json_allowed_and_checked(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'bench/results/oracle-a1-x.json', b'{"tasks": {"sms": {"f1": 0.9}}}\n')
    assert audit(tmp_path, base).returncode == 0
    add(tmp_path, 'bench/results/oracle-a1-y.json', b'{"ids": ["url-0123abcdef"]}\n')
    assert 'eval JSON' in audit(tmp_path, base).stdout


# Round-1 review regressions (Grok 4.7, DeepSeek V4.1 Flash, GLM 5.3, CodeRabbit).
import json
import zlib


def commit_message(repo, path, data, message):
    p = repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', message)


@pytest.mark.parametrize('message', ['leak url-0123abcdef', 'tok ' + 'gh' + 'p_' + 'A' * 30, 'row X-01 said', 'x' * 9000])
def test_commit_message_is_scanned(tmp_path, message):
    base = setup_repo(tmp_path); commit_message(tmp_path, 'a.py', b'print(1)\n', message)
    r = audit(tmp_path, base)
    assert r.returncode == 1 and '<commit message' in r.stdout
    assert 'A' * 30 not in r.stdout + r.stderr


@pytest.mark.parametrize(('path', 'content', 'rule'), [
    ('candidates/x/artifacts/m.joblib', zlib.compress(b'vocab sms-0123abcdef end'), 'item id in artifact'),
    ('candidates/x/artifacts/m.joblib', b'\x78\x9cnot-zlib', 'artifact undecodable'),
    ('research/evals/r/details.json', b'{"n": 12345678901234567890}', 'eval JSON'),
    ('research/evals/r/details.json', b'{"a": 1, "a": 2}', 'eval JSON'),
    ('research/evals/r/details.json', b'{"rows": [[1, 2], [3, 4]]}', 'eval JSON'),
    ('research/evals/r/details.json', b'{"ids": ["X-01", "B-0001"]}', 'eval JSON'),
    ('research/evals/r/details.json', json.dumps({'k': list(range(50)), 'm': {str(i): list(range(50)) for i in range(120)}}).encode(), 'eval JSON'),
    ('research/evals/r/run.log', b'===== 3 passed hidden message text here =====\n', 'non-status log line'),
    ('research/evals/r/app.log', b'[{"verdict": "benign", "score": 1e999}]\n', 'non-status log line'),
    ('research/evals/r/app.log', b'[{"verdict": "benign", "score": 7}]\n', 'non-status log line'),
    ('notes.txt', b'0,tcp,http,SF,181,5450,0,0,0,0,0\n', 'path not uniquely allowlisted'),
    ('data/x.py', b'print(1)\n', 'path not uniquely allowlisted'),
    ('elsewhere/x.py', b'print(1)\n', 'path not uniquely allowlisted'),
    ('models/registry.json', b'{not json', 'config JSON policy'),
    ('candidates/x/config.json', b'{"seed": "sms-0123abcdef"}', 'config JSON policy'),
    ('research/stress/s.jsonl', b'{"id": "a", "label": 1, "text": "t", "source": "uci"}\n', 'synthetic schema policy'),
    ('bench/fixtures/sms.jsonl', b'{"id": "a", "input": "t"}\n', 'synthetic schema policy'),
    ('docs/dump.md', b''.join(b'{"text": "message %d", "label": 1}\n' % i for i in range(25)), 'data-shaped code/docs'),
    ('bench/x.py', b''.join(b'0,tcp,http,SF,181,5450,0,0,0,0,%d\n' % i for i in range(25)), 'data-shaped code/docs'),
    ('code.py', b'API_KEY = ' + b'"abcdefghijklmnop1234"\n', 'secret pattern'),
])
def test_round1_policies(tmp_path, path, content, rule):
    base = setup_repo(tmp_path); add(tmp_path, path, content)
    r = audit(tmp_path, base)
    assert r.returncode == 1 and rule in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize(('path', 'content'), [
    ('bench/requirements-ci.txt', b'numpy==2.5.4\n'),
    ('candidates/x/artifacts/m.joblib', zlib.compress(b'harmless model bytes')),
    ('candidates/x/artifacts/v.joblib', zlib.compress(b'lowercased n-grams x-20 b-2024')),
    ('research/evals/r/tests.log', b'===== 12 passed, 1 warning in 3.41s =====\n'),
    ('research/stress/s.jsonl', b'{"label": 0, "text": "hello"}\n'),
    ('candidates/x/config.json', b'{"threshold": 0.5, "name": "best"}'),
])
def test_round1_allowed(tmp_path, path, content):
    base = setup_repo(tmp_path); add(tmp_path, path, content)
    r = audit(tmp_path, base)
    assert r.returncode == 0, r.stdout + r.stderr


def test_artifact_listed(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', zlib.compress(b'ok'))
    assert 'ARTIFACT candidates/x/artifacts/m.joblib' in audit(tmp_path, base).stdout


def test_symlink_rejected(tmp_path):
    base = setup_repo(tmp_path); (tmp_path / 'link.py').symlink_to('/etc/passwd')
    git(tmp_path, 'add', '.'); git(tmp_path, 'commit', '-qm', 'link')
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'non-regular blob' in r.stdout


def test_merge_side_branch_blob_checked(tmp_path):
    base = setup_repo(tmp_path); git(tmp_path, 'checkout', '-qb', 'side'); add(tmp_path, 'data/raw.jsonl', b'{}\n')
    git(tmp_path, 'checkout', '-q', '-'); add(tmp_path, 'a.py', b'print(1)\n'); git(tmp_path, 'merge', '-q', '--no-edit', 'side')
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'data/raw.jsonl' in r.stdout


def test_non_ancestor_distinct_message(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'a.py', b'print(1)\n'); other = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'checkout', '-q', '--detach', base); add(tmp_path, 'b.py', b'print(2)\n')
    r = audit(tmp_path, other)
    assert r.returncode == 2 and 'not an ancestor' in r.stderr


def test_controller_paths_flagged(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'eval/run_eval.py', b'print(1)\n')
    r = audit(tmp_path, base)
    assert r.returncode == 0 and 'CONTROLLER-OWNED changed (review): eval/run_eval.py' in r.stdout


# Round-2 review regressions (DeepSeek V4.1 Flash, CodeRabbit).
import json as _json
import zlib as _zlib

TRAIL_ID = b'sms-0123' + b'abcdef'

@pytest.mark.parametrize('blob', [
    _zlib.compress(b'harmless') + b'\n' + TRAIL_ID,          # trailing bytes after the stream
    _zlib.compress(b'harmless') + _zlib.compress(TRAIL_ID),   # second concatenated stream
    _zlib.compress(b'harmless' * 100)[:-6],                   # truncated stream
], ids=['trailing', 'concatenated', 'truncated'])
def test_artifact_must_be_one_complete_stream(tmp_path, blob):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', blob)
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'artifact undecodable' in r.stdout

def test_artifact_secret_scanned_after_inflate(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', _zlib.compress(b'k=ghp_' + b'A' * 30))
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'secret pattern' in r.stdout

def test_single_line_record_array_fails(tmp_path):
    rows = _json.dumps([{'text': f'row {i}', 'label': i % 2} for i in range(200)]).encode()
    base = setup_repo(tmp_path); add(tmp_path, 'docs/notes.md', rows + b'\n')
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'data-shaped code/docs content' in r.stdout

def test_escaped_id_in_message_fails(tmp_path):
    base = setup_repo(tmp_path)
    (tmp_path / 'a.py').write_text('x = 1\n'); git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'debug {"id": "\\u0073ms-0123' + 'abcdef"}')
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'item id or data-shaped message' in r.stdout

def test_controller_deletion_listed(tmp_path):
    base0 = setup_repo(tmp_path); add(tmp_path, 'eval/guard/sitecustomize.py', b'x = 1\n')
    base = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'rm', '-q', 'eval/guard/sitecustomize.py'); git(tmp_path, 'commit', '-qm', 'drop guard')
    r = audit(tmp_path, base)
    assert 'CONTROLLER-OWNED deleted (review): eval/guard/sitecustomize.py' in r.stdout


# Round-2 review regressions (Grok 4.7).
import gzip as _gzip

def test_non_zlib_artifact_fails(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', _gzip.compress(b'model ' + TRAIL_ID))
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'artifact undecodable' in r.stdout

def test_raw_pickle_artifact_allowed(tmp_path):
    import pickle
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', pickle.dumps({'w': [0.5, 0.25]}, protocol=4))
    assert audit(tmp_path, base).returncode == 0

def test_indented_csv_counts_as_data(tmp_path):
    line = b'    0,tcp,http,SF,181,5450,0,0,0,0,0,1,0,0\n'
    base = setup_repo(tmp_path); add(tmp_path, 'docs/dump.md', line * 25)
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'data-shaped code/docs content' in r.stdout

def test_unescape_reveals_escaped_text():
    sys.path.insert(0, str(AUDIT.parent)); import audit_push
    escaped = ''.join(f'\\u{ord(c):04x}' for c in 'please send your otp code now')
    assert audit_push.unescape(f'["{escaped}"]') == '["please send your otp code now"]'


# Round-3 review follow-ups (Grok 4.7, DeepSeek V4.1 Flash, CodeRabbit).
def test_escaped_secret_fails(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/config.json', b'{"k": "\\u0067hp_' + b'A' * 30 + b'"}')
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'secret pattern' in r.stdout

def test_pickle_prefixed_gzip_fails(tmp_path):
    base = setup_repo(tmp_path); add(tmp_path, 'candidates/x/artifacts/m.joblib', b'\x80' + _gzip.compress(b'model ' + TRAIL_ID))
    r = audit(tmp_path, base)
    assert r.returncode == 1 and 'artifact undecodable' in r.stdout

def test_one_line_dump_threshold_matches_rows(tmp_path):
    rows = _json.dumps([{'id': f'r{i}', 'text': f'row {i}', 'label': i % 2} for i in range(25)]).encode()
    base = setup_repo(tmp_path); add(tmp_path, 'docs/notes.md', rows + b'\n')
    assert 'data-shaped code/docs content' in audit(tmp_path, base).stdout


def test_india_challenge_exact_schema(tmp_path):
    base = setup_repo(tmp_path)
    row = {'id': 'case-1', 'text': 'sample', 'lang': 'en', 'label': 'benign',
           'category': 'sample', 'pair_id': 'pair-1', 'route': 'sms'}
    add(tmp_path, 'bench/challenge/india_challenge_v1.jsonl', json.dumps(row).encode() + b'\n')
    assert audit(tmp_path, base).returncode == 0
    row['extra'] = 'unexpected'
    add(tmp_path, 'bench/challenge/india_challenge_v1.jsonl', json.dumps(row).encode() + b'\n')
    assert 'synthetic schema policy' in audit(tmp_path, base).stdout


@pytest.mark.parametrize('key,value', [('label', 0), ('route', 'url'), ('lang', 'fr'),
                                       ('text', 3), ('pair_id', 1)])
def test_challenge_bad_values(tmp_path, key, value):
    base = setup_repo(tmp_path)
    row = {'id': 'case-1', 'text': 'sample', 'lang': 'en', 'label': 'benign',
           'category': 'sample', 'pair_id': None, 'route': 'sms'}
    row[key] = value
    add(tmp_path, 'bench/challenge/india_challenge_v1.jsonl', json.dumps(row).encode() + b'\n')
    assert 'synthetic schema policy' in audit(tmp_path, base).stdout


@pytest.mark.parametrize('data,reason', [
    (b'{"id":"a","id":"b"}\n', 'synthetic schema policy'),
    ((json.dumps({'id':'x','text':'t','lang':'en','label':'benign','category':'c','pair_id':None,'route':'sms'}) + '\n').encode() * 501, 'synthetic schema policy'),
    (json.dumps({'id':'x','text':'api_key="' + 'a' * 24 + '"','lang':'en','label':'benign','category':'c','pair_id':None,'route':'sms'}).encode() + b'\n', 'secret pattern'),
])
def test_challenge_rejects_unsafe_contents(tmp_path, data, reason):
    base = setup_repo(tmp_path)
    add(tmp_path, 'bench/challenge/india_challenge_v1.jsonl', data)
    assert reason in audit(tmp_path, base).stdout


def test_challenge_schema_not_allowed_in_fixture_directory(tmp_path):
    base = setup_repo(tmp_path)
    row = {'id': 'case-1', 'text': 'sample', 'lang': 'en', 'label': 'malicious',
           'category': 'sample', 'pair_id': 'pair-1', 'route': 'sms'}
    add(tmp_path, 'bench/fixtures/india_challenge_v1.jsonl', json.dumps(row).encode() + b'\n')
    assert 'synthetic schema policy' in audit(tmp_path, base).stdout


def test_india_v2_dev_path_is_narrow_and_schema_checked():
    from bench.audit_push import SYNTH, synth_ok
    import json
    path = 'bench/dev/india_dev_v2.jsonl'
    row = {'id': 'dev-1', 'text': 'example', 'lang': 'en', 'label': 'benign',
           'category': 'notice', 'pair_id': 'pair-1', 'route': 'sms'}
    def blob(rows):
        return b''.join(json.dumps(r).encode() + b'\n' for r in rows)
    rows = [dict(row, id=f'dev-{i}') for i in range(120)]
    assert SYNTH.fullmatch(path) and synth_ok(path, blob(rows))
    assert not SYNTH.fullmatch('bench/dev/other.jsonl')
    assert not synth_ok(path, blob(rows[:-1]))
    assert not synth_ok(path, blob([*rows[:-1], rows[0]]))
    assert not synth_ok(path, blob([*rows[:-1], dict(rows[-1], extra='bad')]))
    assert not synth_ok(path, blob([*rows[:-1], dict(rows[-1], label='unknown')]))
    assert synth_ok(path, blob([*rows[:-1], dict(rows[-1], route='injection', pair_id=None)]))
    assert not synth_ok(path, blob([*rows[:-1], dict(rows[-1], route='sms', pair_id=None)]))
