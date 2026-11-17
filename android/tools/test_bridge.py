import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'candidates/BEST'), str(ROOT/'android/python')]
import mobile
class Fake:
    def __init__(self, replies): self.replies = iter(replies); self.prompts=[]
    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps({'text':next(self.replies),'stats':{'first_token_ms': 9}})
runner = Fake(["I'm sorry, I cannot help.", 'This message is DANGEROUS. It asks for an OTP.'])
e = mobile.BridgeExplainer(runner)
p = e.prompt('sms', 'Share your OTP at https://example.com', 1, ['asks for an OTP'])
text, stats = e.generate(p)
assert len(runner.prompts) == 2 and stats['retried'] and 'OTP' in text
assert 'https://example[.]com' in p and 'Verdict: DANGEROUS' in p
runner = Fake(["I cannot help.", "I cannot help.", "This message is DANGEROUS. It asks for an OTP."])
e = mobile.BridgeExplainer(runner)
text, stats = e.generate(p)
assert len(runner.prompts) == 3 and stats['evidence_only'] and 'Share your OTP' not in runner.prompts[-1]
print('fake bridge: prompt, retry and evidence-only fallback passed')

# The reference runner's native first_token_ms is an epoch timestamp. The public
# field must instead use elapsed time to its first callback.
from unittest.mock import patch
class NativeStats:
    def to_json_string(self): return json.dumps({'first_token_ms': 1794930926767})
class NativeRunner:
    def reset(self): pass
    def generate(self, prompt, config, token_callback, stats_callback):
        token_callback('This is a test.')
        stats_callback(NativeStats())
reference = object.__new__(mobile.llm.Explainer)
reference.cfg = {}; reference.model_name = 'fake'; reference.runner = NativeRunner()
reference._GC = lambda **kw: kw
with patch.object(mobile.llm.time, 'perf_counter', side_effect=[100.0, 100.25]):
    _, stats = reference._run('prompt')
assert abs(stats['first_token_ms'] - 250.0) < 1e-8, stats
android_fake = Fake(['This is a test.'])
_, stats = mobile.BridgeExplainer(android_fake)._run('prompt')
assert stats['first_token_ms'] == 9
print('Python and Android bridge TTFT fields are callback durations')
