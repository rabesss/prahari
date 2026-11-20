import json

import pytest

from india_challenge import load, summarize


def test_challenge_routes_and_conservative_metrics(tmp_path):
    rows = [
        {'id': 'a', 'text': 'scam', 'lang': 'en', 'label': 'malicious', 'category': 'upi', 'pair_id': 'p', 'route': 'sms'},
        {'id': 'b', 'text': 'receipt', 'lang': 'en', 'label': 'benign', 'category': 'upi', 'pair_id': 'p', 'route': 'sms'},
        {'id': 'c', 'text': 'override', 'lang': 'hi', 'label': 'malicious', 'category': 'injection', 'pair_id': None, 'route': 'injection'},
    ]
    path = tmp_path / 'challenge.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    predictions = {'a': {'label': 1}, 'b': {'label': 'uncertain'}, 'c': {'label': 0}}
    result = summarize(load(path), predictions)
    assert result['sms']['n'] == 2 and result['sms']['coverage'] == 0.5
    assert result['sms']['conservative']['f1'] == pytest.approx(2 / 3)
    assert result['injection']['confusion_decided']['fn'] == 1
    rows[0]['extra'] = 1
    path.write_text(json.dumps(rows[0]) + '\n')
    with pytest.raises(ValueError, match='schema'):
        load(path)
