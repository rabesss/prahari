import json
import hashlib

import pytest

import india_challenge
from india_challenge import load, summarize


def test_challenge_routes_and_conservative_metrics(tmp_path, monkeypatch):
    rows = [
        {'id': 'a', 'text': 'scam', 'lang': 'en', 'label': 'malicious', 'category': 'upi', 'pair_id': 'p', 'route': 'sms'},
        {'id': 'b', 'text': 'receipt', 'lang': 'en', 'label': 'benign', 'category': 'upi', 'pair_id': 'p', 'route': 'sms'},
        {'id': 'c', 'text': 'override', 'lang': 'hi', 'label': 'malicious', 'category': 'injection', 'pair_id': None, 'route': 'injection'},
    ]
    path = tmp_path / 'challenge.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    monkeypatch.setattr(india_challenge, 'CHALLENGE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    predictions = {'a': {'label': 1}, 'b': {'label': 'uncertain'}, 'c': {'label': 0}}
    result = summarize(load(path), predictions)
    assert result['sms']['n'] == 2 and result['sms']['coverage'] == 0.5
    assert result['sms']['conservative']['f1'] == pytest.approx(2 / 3)
    assert result['injection']['confusion_decided']['fn'] == 1
    rows[0]['extra'] = 1
    path.write_text(json.dumps(rows[0]) + '\n')
    monkeypatch.setattr(india_challenge, 'CHALLENGE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match='schema'):
        load(path)


def test_challenge_rejects_wrong_hash(tmp_path):
    path = tmp_path / 'challenge.jsonl'
    path.write_text('{}\n')
    with pytest.raises(ValueError, match='sha256 mismatch'):
        load(path)


def test_explanations_continue_after_consistency_failure(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'candidates' / 'BEST'))
    from triage import detect, llm

    rows = [{'id': ident, 'text': text, 'lang': 'en', 'label': 'malicious',
             'category': 'test', 'pair_id': None, 'route': 'sms'}
            for ident, text in [('a', 'bad'), ('b', 'good')]]
    monkeypatch.setattr(india_challenge, 'load', lambda _: rows)
    monkeypatch.setattr(detect, 'predict_text', lambda texts: [(1, 0.9, ['signal']) for _ in texts])
    class Fake:
        def prompt(self, kind, text, label, evidence): return text
        def generate(self, prompt):
            if prompt == 'bad': raise ValueError('private details')
            return 'Model explanation.', {'generated_tokens': 3}
    monkeypatch.setattr(llm, 'Explainer', Fake)
    sample, out = tmp_path / 'sample', tmp_path / 'result.json'
    sample.write_text('a\nb\n')
    monkeypatch.setattr(sys, 'argv', ['india_challenge', 'candidates/BEST', 'unused', '--sample', str(sample), '--out', str(out)])
    india_challenge.main()
    explanations = json.loads(out.read_text())['explanations']
    assert explanations['a']['explanation_status'] == 'failed' and explanations['a']['explanation_error']
    assert 'text' not in explanations['a'] and 'stats' not in explanations['a']
    assert explanations['b']['explanation_status'] == 'success' and explanations['b']['text'] == 'Model explanation.'
def test_explicit_adaptive_dataset_hash_is_verified(tmp_path):
    row = {'id': 'a', 'text': 'sample', 'lang': 'en', 'label': 'benign',
           'category': 'upi', 'pair_id': 'p', 'route': 'sms'}
    path = tmp_path / 'adaptive.jsonl'
    path.write_text(json.dumps(row) + '\n')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert load(path, expected_sha256=digest) == [row]
    with pytest.raises(ValueError, match='sha256 mismatch'):
        load(path, expected_sha256='0' * 64)
    with pytest.raises(ValueError, match='sha256 mismatch'):
        load(path)
