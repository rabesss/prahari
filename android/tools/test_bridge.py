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
