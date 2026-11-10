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
