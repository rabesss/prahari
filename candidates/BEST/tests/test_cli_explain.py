import json
from types import SimpleNamespace

from triage import cli, llm


def test_explain_keeps_rows_after_consistency_failure(tmp_path, monkeypatch):
    class Fake:
        def prompt(self, kind, inp, lab, ev): return inp
        def generate(self, prompt):
            if prompt == 'bad': raise ValueError('private details')
            return 'Model explanation.', {'generated_tokens': 3}

    monkeypatch.setattr(llm, 'Explainer', Fake)
    monkeypatch.setattr(cli.detect, 'classify_any', lambda *args: (1, 0.9, ['signal']))
    inp, out = tmp_path / 'in.jsonl', tmp_path / 'out.jsonl'
    inp.write_text(''.join(json.dumps({'id': i, 'kind': 'flow', 'input': text}) + '\n'
                           for i, text in enumerate(('bad', 'good'))))
    cli.cmd_explain(SimpleNamespace(inp=inp, out=out))
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r['id'] for r in rows] == [0, 1]
    assert rows[0]['explanation_status'] == 'failed' and rows[0]['explanation_error']
    assert 'explanation' not in rows[0] and 'llm' not in rows[0]
    assert rows[1]['explanation_status'] == 'success' and rows[1]['explanation'] == 'Model explanation.'
