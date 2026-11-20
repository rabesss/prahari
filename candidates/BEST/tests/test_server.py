from concurrent.futures import ThreadPoolExecutor
import threading
import time
from app import server
from triage import llm


def test_no_explanation_keeps_actions_and_category(monkeypatch):
    monkeypatch.setattr(server.detect, 'classify_any', lambda *_: ('uncertain', 0.5, ['signal']))
    result = server.triage('flow', 'normal port scan', False)
    assert result['actions'] and result['category'] and 'IT team' in result['actions'][0]


def test_failed_init_keeps_result(monkeypatch):
    monkeypatch.setattr(server.detect, 'classify_any', lambda *_: (1, 0.9, ['signal']))
    monkeypatch.setattr(server, '_ex', None)
    def fail(): raise RuntimeError('private details')
    monkeypatch.setattr(llm, 'Explainer', fail)
    result = server.triage('flow', 'port scan', True)
    assert result['actions'] and result['category'] and result['evidence']
    assert result['explanation_error'] and 'private details' not in str(result)


def test_generation_serialized(monkeypatch):
    monkeypatch.setattr(server.detect, 'classify_any', lambda *_: (1, 0.9, ['signal']))
    state = {'active': 0, 'max': 0}
    monitor = threading.Lock()
    class Fake:
        def prompt(self, *args): return 'prompt'
        def generate(self, prompt):
            with monitor:
                state['active'] += 1
                state['max'] = max(state['active'], state['max'])
            time.sleep(0.05)
            with monitor: state['active'] -= 1
            return 'explanation', {}
    monkeypatch.setattr(server, '_ex', Fake())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: server.triage('flow', 'port scan', True), range(2)))
    assert state['max'] == 1 and all(r['explanation'] == 'explanation' for r in results)


def test_generate_failure(monkeypatch):
    monkeypatch.setattr(server.detect, 'classify_any', lambda *_: (1, 0.9, ['signal']))
    class Fake:
        def prompt(self, *args): return 'prompt'
        def generate(self, prompt): raise RuntimeError('failure')
    monkeypatch.setattr(server, '_ex', Fake())
    result = server.triage('flow', 'port scan', True)
    assert result['explanation_error'] and result['actions']


def test_init_serialized(monkeypatch):
    monkeypatch.setattr(server.detect, 'classify_any', lambda *_: (1, 0.9, ['signal']))
    monkeypatch.setattr(server, '_ex', None)
    created = []
    class Fake:
        def __init__(self):
            created.append(1)
            time.sleep(0.05)
        def prompt(self, *args): return 'prompt'
        def generate(self, prompt): return 'explanation', {}
    monkeypatch.setattr(llm, 'Explainer', Fake)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: server.triage('flow', 'port scan', True), range(2)))
    assert len(created) == 1 and all('explanation' in r for r in results)


def test_benign_prompt_keeps_verdict_for_filter():
    prompt = llm.Explainer.prompt(object(), 'flow', 'scheduled backup', 0, [])
    assert llm._prompt_verdict(prompt) == 0
    assert 'No risk found' in prompt
