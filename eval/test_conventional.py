import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conventional import metrics
from run_eval import det_metrics
from consistency_v2 import consistent
import pytest


def test_all_decided():
    m = metrics({'a': 1, 'b': 0, 'c': 1, 'd': 0}, {'a': 1, 'b': 0, 'c': 0, 'd': 1})
    assert m['decided'] == 4 and m['coverage'] == 1
    assert m['conditional'] == m['conservative'] == {'precision': .5, 'recall': .5, 'f1': .5, 'fpr': .5}


def test_all_abstain():
    m = metrics({'a': 1, 'b': 0}, {'a': 'uncertain', 'b': 'uncertain'})
    assert m['uncertain'] == 2 and m['coverage'] == 0
    assert all(v is None for v in m['conditional'].values())
    assert m['conservative']['recall'] == 0 and m['conservative']['fpr'] == 1


def test_mixed_invalid_missing():
    m = metrics({'a': 1, 'b': 0, 'c': 1, 'd': 0, 'e': 0}, {'a': 1, 'b': 0, 'c': 'uncertain', 'd': 'bad'})
    assert (m['decided'], m['uncertain'], m['invalid']) == (2, 1, 2)
    assert m['conditional']['f1'] == 1 and m['conservative']['f1'] == .4
    assert m['conservative']['fpr'] == 2/3


def test_empty_positive_class_and_empty_dataset():
    m = metrics({'a': 0}, {'a': 0})
    assert m['conditional']['recall'] is None and 'conditional.recall' in m['undefined_reasons']
    assert metrics({}, {})['coverage'] is None


def test_proxy_unchanged_for_identical_predictions():
    gold, preds = {'a': 1, 'b': 0}, {'a': 'uncertain', 'b': 0}
    before = det_metrics(gold, preds)
    metrics(gold, preds)
    assert det_metrics(gold, preds) == before


@pytest.mark.parametrize('verdict,text,expected', [
    (0, 'No risk found for this message.', True),
    (0, 'Nothing suspicious was found.', True),
    (0, 'This is safe.', True),
    (1, 'This is safe.', False),
    (1, 'This is not safe.', True),
    (1, 'This is not very safe.', True),
    (1, 'This is not really safe.', True),
    (0, 'This is not necessarily safe.', True),
    (1, 'This is not necessarily safe.', True),
    (0, 'This is not necessarily dangerous.', True),
    (1, 'This is not necessarily dangerous.', True),
    (0, 'This is not really safe.', False),
    (0, 'This is not very safe.', False),
    (1, 'This is very safe.', False),
    (0, 'This is very safe.', True),
    (0, 'This is not safe.', False),
    (1, 'Not safe.', True),
    (0, 'Not safe.', False),
    (1, 'No risk found, but be careful.', False),
    (0, 'No risk found, but be careful.', True),
    (1, 'Do not click, it is safe.', False),
    (0, 'Do not click, it is safe.', True),
    (0, 'No risk found, but this is dangerous.', False),
    (1, 'No risk found, but this is dangerous.', False),
    (0, 'Be cautious of phishing scams that may be disguised as a bank website.', True),
    (0, 'This is a phishing scam.', False),
    (0, 'This is not dangerous.', True),
    (1, 'This is not dangerous.', False),
])
def test_consistency_v2(verdict, text, expected):
    assert consistent(verdict, text) is expected


def test_duplicate_ids_match_proxy_last_prediction(tmp_path, monkeypatch):
    import json
    import conventional
    from types import SimpleNamespace
    monkeypatch.setattr(conventional, 'DEFAULT', tmp_path)
    monkeypatch.setattr(conventional, 'sandbox_env', lambda _: {})
    def run(cmd, **kwargs):
        out = Path(cmd[cmd.index('--out') + 1])
        out.write_text('\n'.join(json.dumps(r) for r in [
            {'id': 'duplicate', 'label': 0}, {'id': 'duplicate', 'label': 1}]) + '\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(conventional.subprocess, 'run', run)
    rows = [{'id': 'duplicate', 'text': 'first', 'label': 0},
            {'id': 'duplicate', 'text': 'second', 'label': 1}]
    result = conventional.evaluate(tmp_path, 'sms', rows)
    assert result['input_rows'] == 2 and result['duplicate_input_rows'] == 1
    assert result['n'] == 1 and result['confusion_decided']['tp'] == 1


def test_missing_output_file_counts_invalid(tmp_path, monkeypatch):
    import conventional
    from types import SimpleNamespace
    monkeypatch.setattr(conventional, 'DEFAULT', tmp_path)
    monkeypatch.setattr(conventional, 'sandbox_env', lambda _: {})
    monkeypatch.setattr(conventional.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    result = conventional.evaluate(tmp_path, 'sms', [{'id': 'x', 'text': 'a', 'label': 1}])
    assert result['invalid'] == 1 and result['conservative']['recall'] == 0
